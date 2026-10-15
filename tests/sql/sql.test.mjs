// Pruebas de los scripts y funciones SQL contra un Postgres de verdad (PGlite = Postgres 18 en WebAssembly).
// Se ejecutan con:  cd tests/sql && npm ci && npm test      (o desde Python: tests/test_sql_runtime.py)
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PGlite } from "@electric-sql/pglite";
import { pgcrypto } from "@electric-sql/pglite/contrib/pgcrypto";

const DB_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../db");
const read = (f) => fs.readFileSync(path.join(DB_DIR, f), "utf8");
const BASE = ["schema.sql", "migrations/036_despacho_mrp.sql"];
const PHASES = ["migrations/041_fase_b.sql", "migrations/042_fase_c.sql", "migrations/043_fase_e.sql", "migrations/044_fase_f.sql", "migrations/045_empresa_igv.sql"];
const CLOSE = "migrations/040_cerrar_base.sql";

/** Base nueva con los roles de Supabase y los scripts indicados (en ese orden). */
async function build(files = [...BASE, ...PHASES]) {
  const db = new PGlite({ extensions: { pgcrypto } });
  await db.exec(`
    create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls;
  `);
  for (const file of files) {
    try {
      await db.exec(read(file));
    } catch (error) {
      throw new Error(`${file}: ${error.message}`);
    }
  }
  await db.exec("grant all on all tables in schema public to service_role; grant all on all sequences in schema public to service_role;");
  return db;
}

const one = async (db, sql, params) => (await db.query(sql, params)).rows[0];
const val = async (db, sql, params) => Object.values(await one(db, sql, params))[0];

/** Un material, una obra, un proveedor y una orden con dos líneas (10 de cemento y 5 de arena). */
async function seed(db) {
  const cement = (await one(db, "insert into materials (category, name, metric_label) values ('Obra', 'Cemento', 'bolsa') returning id")).id;
  const sand = (await one(db, "insert into materials (category, name, metric_label) values ('Obra', 'Arena', 'm3') returning id")).id;
  const site = (await one(db, "insert into project_sites (name) values ('Torre') returning id")).id;
  const supplier = (await one(db, "insert into suppliers (name) values ('Norte') returning id")).id;
  const order = (await one(db, "insert into purchase_orders (code, supplier_id, supplier_name, project_site_id) values ('OC-0001', $1, 'Norte', $2) returning id", [supplier, site])).id;
  const line1 = (await one(db, "insert into purchase_order_items (order_id, material_id, material_name, quantity, unit_price) values ($1, $2, 'Cemento', 10, 25) returning id", [order, cement])).id;
  const line2 = (await one(db, "insert into purchase_order_items (order_id, material_id, material_name, quantity, unit_price) values ($1, $2, 'Arena', 5, 60) returning id", [order, sand])).id;
  return { cement, sand, site, supplier, order, line1, line2 };
}

const stockOf = (db, material) => val(db, "select stock from stock_levels where material_id = $1", [material]).then(Number);
const receive = (db, ids, receipts, extra = []) =>
  db.query("select receive_order($1, $2::jsonb, 'admin', $3, $4, $5) as status", [ids.order, JSON.stringify(receipts), ...(extra.length ? extra : [null, null, null])]);

// ---------------------------------------------------------------------------------------------------------------------

test("todos los scripts corren sin errores, también dos veces (son idempotentes)", async () => {
  const db = await build();
  for (const file of PHASES) await db.exec(read(file));
  await db.exec(read("migrations/036_despacho_mrp.sql"));   // volver a correr uno viejo no debe duplicar las funciones nuevas
  assert.equal(await val(db, "select count(*) from pg_proc where proname = 'receive_order'"), 1, "queda una sola versión de receive_order");
  assert.equal(await val(db, "select count(*) from pg_proc where proname = 'create_dispatch'"), 1, "queda una sola versión de create_dispatch");
});

test("schema.sql solo basta para una instalación nueva y se puede repetir", async () => {
  const db = await build(["schema.sql"]);
  await db.exec(read("schema.sql"));
  for (const table of ["materials", "inventory_counts", "order_receipts", "attachments", "price_history", "dispatch_vouchers"]) {
    assert.equal(await val(db, "select count(*) from pg_tables where schemaname = 'public' and tablename = $1", [table]), 1, table);
  }
  for (const view of ["stock_levels", "site_consumption", "dashboard_stats"]) {
    assert.equal(await val(db, "select count(*) from pg_views where schemaname = 'public' and viewname = $1", [view]), 1, view);
  }
  assert.equal(await val(db, "select count(*) from pg_proc where proname = 'receive_order'"), 1);
  assert.equal(await val(db, "select count(*) from pg_proc where proname = 'create_dispatch'"), 1);
  const ids = await seed(db);
  assert.equal((await receive(db, ids, { [ids.line1]: 10, [ids.line2]: 5 })).rows[0].status, "recibida");
});

test("volver a correr 036 en una base cerrada no la reabre", async () => {
  const db = await build([...BASE, ...PHASES, CLOSE, "migrations/036_despacho_mrp.sql"]);
  await db.exec("set role anon");
  for (const table of ["price_history", "dispatch_vouchers", "stock_levels"]) {
    await assert.rejects(db.query(`select * from ${table}`), /permission denied/, table);
  }
  await db.exec("reset role");
  assert.equal(await val(db, "select count(*) from pg_proc where proname = 'receive_order'"), 1);
});

test("receive_order: recepción parcial y luego completa, con su documento", async () => {
  const db = await build();
  const ids = await seed(db);
  assert.equal((await receive(db, ids, { [ids.line1]: 4 }, ["Luis", " T001-77 ", "2 rotas"])).rows[0].status, "parcial");
  assert.equal(await stockOf(db, ids.cement), 4);
  const receipt = await one(db, "select * from order_receipts where order_id = $1", [ids.order]);
  assert.equal(receipt.document_ref, "T001-77");
  assert.equal(receipt.delivered_by, "Luis");
  assert.equal(receipt.notes, "2 rotas");
  const move = await one(db, "select * from stock_movements where order_id = $1", [ids.order]);
  assert.equal(move.movement_type, "recepcion");
  assert.equal(move.receipt_id, receipt.id);
  assert.match(move.note, /T001-77/);

  assert.equal((await receive(db, ids, { [ids.line1]: 6, [ids.line2]: 5 })).rows[0].status, "recibida");
  assert.equal(await stockOf(db, ids.cement), 10);
  assert.equal(await stockOf(db, ids.sand), 5);
  assert.equal(await val(db, "select status from purchase_orders where id = $1", [ids.order]), "recibida");
  assert.equal(await val(db, "select count(*) from order_receipts where order_id = $1", [ids.order]), 2);
});

test("receive_order: no deja pasarse, ni recibir en órdenes canceladas o inexistentes, y es todo o nada", async () => {
  const db = await build();
  const ids = await seed(db);
  await assert.rejects(receive(db, ids, { [ids.line1]: 11 }), /más de lo pedido/);
  // la primera línea es válida y la segunda no: no debe quedar nada de la primera
  await assert.rejects(receive(db, ids, { [ids.line1]: 3, [ids.line2]: 99 }), /más de lo pedido/);
  assert.equal(await val(db, "select count(*) from stock_movements"), 0);
  assert.equal(Number(await val(db, "select received_qty from purchase_order_items where id = $1", [ids.line1])), 0);
  assert.equal(await val(db, "select count(*) from order_receipts"), 0);
  // una línea de otra orden
  const other = (await one(db, "insert into purchase_orders (code, supplier_name) values ('OC-0002', 'X') returning id")).id;
  const foreign = (await one(db, "insert into purchase_order_items (order_id, material_name, quantity, unit_price) values ($1, 'Y', 1, 1) returning id", [other])).id;
  await assert.rejects(receive(db, ids, { [foreign]: 1 }), /no pertenece/);
  await assert.rejects(db.query("select receive_order('00000000-0000-0000-0000-000000000001', '{}'::jsonb, 'a')"), /no existe/);
  await db.query("update purchase_orders set status = 'cancelada' where id = $1", [ids.order]);
  await assert.rejects(receive(db, ids, { [ids.line1]: 1 }), /cancelada/);
  // cantidades 0 o negativas se ignoran
  await db.query("update purchase_orders set status = 'pendiente' where id = $1", [ids.order]);
  await receive(db, ids, { [ids.line1]: 0, [ids.line2]: -3 });
  assert.equal(await val(db, "select count(*) from stock_movements"), 0);
});

test("create_dispatch: genera el vale con su etapa, descuenta el stock y numera los vales", async () => {
  const db = await build();
  const ids = await seed(db);
  await receive(db, ids, { [ids.line1]: 10, [ids.line2]: 5 });
  const lines = JSON.stringify([{ material_id: ids.cement, quantity: 4, note: "" }, { material_id: ids.sand, quantity: 1 }]);
  const code = await val(db, "select create_dispatch($1, null, 'Juan', 'losa', 'admin', $2::jsonb, 'Cimentación')", [ids.site, lines]);
  assert.equal(code, "VS-0001");
  assert.equal(await stockOf(db, ids.cement), 6);
  const voucher = await one(db, "select * from dispatch_vouchers where code = 'VS-0001'");
  assert.equal(voucher.stage, "Cimentación");
  assert.equal(voucher.requested_by, "Juan");
  assert.equal(voucher.site_name, "Torre");
  const moves = (await db.query("select * from stock_movements where voucher_id = $1", [voucher.id])).rows;
  assert.equal(moves.length, 2);
  assert.ok(moves.every((m) => m.kind === "salida" && m.movement_type === "despacho" && m.stage === "Cimentación"));
  assert.equal(await val(db, "select create_dispatch($1, null, null, null, 'a', $2::jsonb)", [ids.site, lines]), "VS-0002");
  assert.equal(await val(db, "select stage from dispatch_vouchers where code = 'VS-0002'"), null);
});

test("create_dispatch: sin stock suficiente no registra nada (ni el vale)", async () => {
  const db = await build();
  const ids = await seed(db);
  await receive(db, ids, { [ids.line1]: 3 });
  const lines = JSON.stringify([{ material_id: ids.cement, quantity: 2 }, { material_id: ids.cement, quantity: 2 }]);
  await assert.rejects(db.query("select create_dispatch($1, null, null, null, 'a', $2::jsonb)", [ids.site, lines]), /Stock insuficiente/);
  assert.equal(await val(db, "select count(*) from dispatch_vouchers"), 0);
  assert.equal(await stockOf(db, ids.cement), 3);
  await assert.rejects(db.query("select create_dispatch('00000000-0000-0000-0000-000000000001', null, null, null, 'a', $1::jsonb)", [lines]), /obra no existe/);
  await assert.rejects(db.query("select create_dispatch($1, null, null, null, 'a', '[]'::jsonb)", [ids.site]), /no tiene materiales/);
});

test("triggers: stock nunca negativo, órdenes con recepción no se borran y los precios dejan historial", async () => {
  const db = await build();
  const ids = await seed(db);
  await assert.rejects(
    db.query("insert into stock_movements (material_id, kind, quantity) values ($1, 'salida', 1)", [ids.cement]),
    /Stock insuficiente/,
  );
  await receive(db, ids, { [ids.line1]: 1 });
  await assert.rejects(db.query("delete from purchase_orders where id = $1", [ids.order]), /ya recibió material/);
  const spare = (await one(db, "insert into purchase_orders (code, supplier_name) values ('OC-0009', 'X') returning id")).id;
  await db.query("delete from purchase_orders where id = $1", [spare]); // sin recepciones sí se puede

  await db.query("insert into supplier_materials (supplier_id, material_id, price) values ($1, $2, 10)", [ids.supplier, ids.cement]);
  await db.query("update supplier_materials set price = 12 where supplier_id = $1", [ids.supplier]);
  await db.query("update supplier_materials set available = false where supplier_id = $1", [ids.supplier]); // sin cambio de precio
  const history = (await db.query("select price from price_history order by recorded_at, id")).rows.map((r) => Number(r.price));
  assert.deepEqual(history, [10, 12]);
  assert.notEqual(await val(db, "select price_updated_at from supplier_materials"), null);
});

test("vistas: stock_levels, site_consumption (despachos − devoluciones) y dashboard_stats", async () => {
  const db = await build();
  const ids = await seed(db);
  await receive(db, ids, { [ids.line1]: 10, [ids.line2]: 5 });
  const lines = (qty) => JSON.stringify([{ material_id: ids.cement, quantity: qty }]);
  await db.query("select create_dispatch($1, null, 'J', null, 'a', $2::jsonb, 'Cimentación')", [ids.site, lines(4)]);
  await db.query("select create_dispatch($1, null, 'J', null, 'a', $2::jsonb)", [ids.site, lines(2)]);
  // devolución de obra (cuenta), merma (no), devolución a proveedor (no) y conteo (no)
  await db.query("insert into stock_movements (material_id, project_site_id, kind, quantity, movement_type, stage) values ($1, $2, 'entrada', 1, 'devolucion', 'Cimentación')", [ids.cement, ids.site]);
  await db.query("insert into stock_movements (material_id, kind, quantity, movement_type) values ($1, 'salida', 1, 'merma')", [ids.cement]);
  await db.query("insert into stock_movements (material_id, kind, quantity, movement_type) values ($1, 'salida', 1, 'devolucion_proveedor')", [ids.cement]);
  await db.query("insert into stock_movements (material_id, kind, quantity, movement_type) values ($1, 'entrada', 5, 'conteo')", [ids.cement]);

  assert.equal(await stockOf(db, ids.cement), 10 - 4 - 2 + 1 - 1 - 1 + 5);
  const rows = (await db.query("select stage, quantity from site_consumption where material_id = $1 order by stage", [ids.cement])).rows;
  assert.deepEqual(rows.map((r) => [r.stage, Number(r.quantity)]), [["", 2], ["Cimentación", 3]]);
  assert.equal((await db.query("select * from site_consumption")).rows.length, 2);
  await db.query("insert into stock_movements (material_id, project_site_id, kind, quantity, movement_type) values ($1, $2, 'entrada', 2, 'devolucion')", [ids.cement, ids.site]);
  assert.equal(
    (await db.query("select * from site_consumption where material_id = $1 and stage = ''", [ids.cement])).rows.length, 0,
    "las filas que quedan en cero no aparecen",
  );

  await db.query("update materials set min_stock = 100 where id = $1", [ids.cement]);
  const stats = await one(db, "select * from dashboard_stats");
  assert.equal(Number(stats.materials), 2);
  assert.equal(Number(stats.suppliers), 1);
  assert.equal(Number(stats.orders_open), 0);   // la orden quedó recibida
  assert.equal(Number(stats.materials_in_stock), 2);
  assert.equal(Number(stats.low_stock), 1);
  assert.equal(Number(stats.materials_without_supplier), 2);
  assert.equal(Number(stats.dispatches_month), 2);
});

test("040_cerrar_base: la clave pública deja de ver todo y la de servicio sigue funcionando", async () => {
  const db = await build([...BASE, ...PHASES, CLOSE]);
  const ids = await seed(db);
  await db.exec("set role anon");
  for (const table of ["materials", "users", "stock_movements", "inventory_counts", "order_receipts", "attachments", "site_consumption", "dashboard_stats", "stock_levels"]) {
    await assert.rejects(db.query(`select * from ${table}`), /permission denied/, `anon no debe leer ${table}`);
  }
  await assert.rejects(db.query("insert into materials (category, name) values ('a', 'b')"), /permission denied/);
  await assert.rejects(db.query("select receive_order($1, '{}'::jsonb, 'a')", [ids.order]), /permission denied/);
  await assert.rejects(db.query("select create_dispatch($1, null, null, null, 'a', '[]'::jsonb)", [ids.site]), /permission denied/);
  await db.exec("reset role; set role service_role");
  assert.equal(await val(db, "select count(*) from materials"), 2);
  assert.equal((await receive(db, ids, { [ids.line1]: 10, [ids.line2]: 5 })).rows[0].status, "recibida");
  assert.equal(await val(db, "select count(*) from site_consumption"), 0);
  await db.exec("reset role");
});

test("040 antes que la Fase B: lo que se agrega después nace cerrado", async () => {
  const db = await build([...BASE, CLOSE, ...PHASES]);
  await db.exec("set role anon");
  for (const table of ["inventory_counts", "inventory_count_lines", "order_receipts", "attachments", "site_consumption", "dashboard_stats"]) {
    await assert.rejects(db.query(`select * from ${table}`), /permission denied/, `anon no debe leer ${table}`);
  }
  await assert.rejects(db.query("select receive_order('00000000-0000-0000-0000-000000000001', '{}'::jsonb)"), /permission denied/);
  await db.exec("reset role");
});

test("040b_reabrir_base_emergencia deshace el cierre", async () => {
  const db = await build([...BASE, ...PHASES, CLOSE, "migrations/040b_reabrir_base_emergencia.sql"]);
  await db.exec("set role anon");
  assert.equal(await val(db, "select count(*) from materials"), 0);
  await db.query("insert into materials (category, name) values ('a', 'b')");
  assert.equal(await val(db, "select count(*) from site_consumption"), 0);
  await db.exec("reset role");
});

test("restricciones de las órdenes y presupuestos por etapa", async () => {
  const db = await build();
  const ids = await seed(db);
  await assert.rejects(db.query("update purchase_orders set currency = 'EUR' where id = $1", [ids.order]), /currency_chk/);
  await assert.rejects(db.query("update purchase_orders set tax_rate = 2 where id = $1", [ids.order]), /tax_rate_chk/);
  await assert.rejects(db.query("update purchase_orders set exchange_rate = 0 where id = $1", [ids.order]), /exchange_rate_chk/);
  await assert.rejects(db.query("update suppliers set lead_time_days = -1"), /lead_time_chk/);
  await assert.rejects(db.query("update suppliers set min_order_amount = -5"), /min_order_chk/);
  await db.query("insert into site_budgets (project_site_id, material_id, planned_qty, stage) values ($1, $2, 5, 'A')", [ids.site, ids.cement]);
  await db.query("insert into site_budgets (project_site_id, material_id, planned_qty, stage) values ($1, $2, 5, 'B')", [ids.site, ids.cement]);
  await assert.rejects(db.query("insert into site_budgets (project_site_id, material_id, planned_qty, stage) values ($1, $2, 1, 'A')", [ids.site, ids.cement]), /duplicate key/);
  await assert.rejects(db.query("insert into stock_movements (material_id, kind, quantity) values ($1, 'entrada', 0)", [ids.cement]), /qty_chk/);
});

test("audit_log guarda el detalle de los cambios (antes → después) como jsonb", async () => {
  const db = await build();
  const changes = [{ field: "Precio", before: "10", after: "12" }];
  await db.query("insert into audit_log (actor, summary, entity_type, entity_id, changes) values ('admin', 'x', 'catalogo', 's:m', $1::jsonb)", [JSON.stringify(changes)]);
  await db.query("insert into audit_log (actor, summary) values ('admin', 'sin detalle')");
  const rows = (await db.query("select summary, entity_type, changes from audit_log order by summary")).rows;
  assert.deepEqual(rows.find((r) => r.summary === "x").changes, changes);
  assert.equal(rows.find((r) => r.summary === "sin detalle").changes, null);
});

test("empresa, RUC e IGV: una sola fila de empresa, RUC de 11 dígitos y columnas de la orden", async () => {
  const db = await build();
  await db.query("insert into company_profile (legal_name, ruc) values ('Constructora SAC', '20131312955')");
  await assert.rejects(db.query("insert into company_profile (legal_name) values ('Otra')"), /duplicate key|singleton/);   // una sola fila
  await assert.rejects(db.query("update company_profile set ruc = '123'"), /ruc/);
  await assert.rejects(db.query("update company_profile set ruc = '2013131295A'"), /ruc/);
  await db.query("update company_profile set ruc = null");
  const ids = await seed(db);
  await db.query("update suppliers set ruc = '20100070970' where id = $1", [ids.supplier]);
  await assert.rejects(db.query("update suppliers set ruc = '2010007097' where id = $1", [ids.supplier]), /ruc_chk/);
  const order = await one(db, "select prices_include_tax, payment_terms from purchase_orders where id = $1", [ids.order]);
  assert.equal(order.prices_include_tax, false);
  assert.equal(order.payment_terms, null);
  await db.query("update purchase_orders set prices_include_tax = true, payment_terms = 'Crédito 30 días', tax_rate = 0.18 where id = $1", [ids.order]);
});

test("045 en una base cerrada: company_profile nace cerrada", async () => {
  const db = await build([...BASE, ...PHASES.slice(0, -1), CLOSE, "migrations/045_empresa_igv.sql"]);
  await db.exec("set role anon");
  await assert.rejects(db.query("select * from company_profile"), /permission denied/);
  await db.exec("reset role");
  await db.exec("set role service_role");
  assert.equal(await val(db, "select count(*) from company_profile"), 0);
  await db.exec("reset role");
});
