"""Búsqueda de direcciones: variantes, alias, orden de candidatos, respaldo con Photon y memoria de resultados (sin red)."""
import unittest
from unittest import mock

from utils import geocode


def cand(lat, lon, name, source="OpenStreetMap"):
    return {"lat": lat, "lon": lon, "display_name": name, "source": source}


class VariantTests(unittest.TestCase):
    def test_abbreviations_are_expanded(self):
        text = geocode._normalize_query("Av. Arequipa 1200, Jr. Cusco 50 , Urb. Los Pinos")
        self.assertEqual(text, "Avenida Arequipa 1200, Jirón Cusco 50, Urbanización Los Pinos")
        self.assertEqual(geocode._normalize_query("av larco 1301"), "Avenida larco 1301")
        self.assertEqual(geocode._normalize_query("Avenida Sta. Rosa"), "Avenida Santa Rosa")

    def test_variants_go_from_specific_to_general_without_repeats(self):
        variants = geocode.query_variants("Jockey Plaza, Av. Javier Prado Este 4200, Santiago de Surco")
        self.assertEqual(variants[0], "Jockey Plaza, Avenida Javier Prado Este 4200, Santiago de Surco")
        self.assertIn("Jockey Plaza, Santiago de Surco", variants)                  # nombre del lugar + distrito
        self.assertIn("Avenida Javier Prado Este 4200, Santiago de Surco", variants)  # sin el nombre del local
        self.assertIn("Jockey Plaza Avenida Javier Prado Este Santiago de Surco", variants)   # sin el número de puerta
        self.assertEqual(len(variants), len({v.lower() for v in variants}))

    def test_lima_is_assumed_only_when_no_city_is_written(self):
        self.assertTrue(any(v.endswith("Lima, Perú") for v in geocode.query_variants("Av. Salaverry 2370")))
        self.assertFalse(any("Lima, Perú" in v for v in geocode.query_variants("Plaza de Armas, Cusco")))
        self.assertFalse(any("Lima, Perú" in v for v in geocode.query_variants("Av. Arequipa 100, Lima")))

    def test_alias_for_places_openstreetmap_names_differently(self):
        self.assertEqual(geocode.query_variants("Plaza de Armas, Lima")[0], "Plaza Mayor, Lima")
        self.assertEqual(geocode.query_variants("Plaza de Armas, Cusco")[0], "Plaza de Armas, Cusco")
        self.assertIn("Aeropuerto Internacional Jorge Chávez", geocode.query_variants("aeropuerto jorge chavez")[0] + geocode.query_variants("aeropuerto jorge chávez")[0])


class RankTests(unittest.TestCase):
    def test_candidate_with_the_house_number_goes_first(self):
        found = [cand(-12.08, -76.97, "Avenida Javier Prado Este, Surco"), cand(-12.09, -76.98, "4200, Avenida Javier Prado Este, Surco")]
        ranked = geocode._rank("Av. Javier Prado Este 4200", found)
        self.assertIn("4200", ranked[0]["display_name"])
        self.assertEqual(len(ranked), 2)                                       # nunca descarta

    def test_lima_area_first_unless_another_city_is_named(self):
        far, near = cand(-9.5, -77.5, "Av. Venezuela, Huaraz"), cand(-12.057, -77.084, "Av. Venezuela, Lima")
        self.assertEqual(geocode._rank("Av. Venezuela", [far, near])[0], near)
        self.assertEqual(geocode._rank("Av. Venezuela, Huaraz", [far, near])[0], far)

    def test_order_is_kept_inside_each_group(self):
        a, b, c = (cand(-12.05, -77.04 - i / 100, f"calle {i}") for i in range(3))
        self.assertEqual(geocode._rank("calle", [a, b, c]), [a, b, c])


class SearchTests(unittest.TestCase):
    def setUp(self):
        geocode._cache.clear()
        patcher = mock.patch.object(geocode.time, "sleep", lambda s: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_first_variant_that_answers_wins_and_nothing_else_is_asked(self):
        with mock.patch.object(geocode, "_nominatim", return_value=[cand(-12.1, -77.03, "Larcomar")]) as nom, mock.patch.object(geocode, "_photon", return_value=[cand(-12.1, -77.03, "Larcomar (Photon)", "Photon")]):
            found = geocode.search_address("Larcomar, Miraflores")
        self.assertEqual(nom.call_count, 1)
        self.assertEqual(found[0]["display_name"], "Larcomar")

    def test_photon_completes_when_openstreetmap_finds_nothing(self):
        with mock.patch.object(geocode, "_nominatim", return_value=[]) as nom, mock.patch.object(geocode, "_photon", return_value=[cand(-12.05, -77.04, "Plaza San Martín", "Photon"), cand(-12.06, -77.05, "Otro", "Photon")]):
            found = geocode.search_address("Plaza San Martin, Av. Nicolas de Pierola 100, Lima")
        self.assertEqual(nom.call_count, 3)                                     # probó tres variantes
        self.assertEqual({c["source"] for c in found}, {"Photon"})

    def test_duplicates_closer_than_about_100_m_are_dropped(self):
        two = [cand(-12.1000, -77.0300, "A"), cand(-12.1003, -77.0301, "A de nuevo"), cand(-12.2, -77.1, "B")]
        with mock.patch.object(geocode, "_nominatim", return_value=two), mock.patch.object(geocode, "_photon", return_value=[]):
            found = geocode.search_address("algo")
        self.assertEqual([c["display_name"] for c in found], ["A", "B"])

    def test_results_are_remembered_but_failures_are_not(self):
        with mock.patch.object(geocode, "_nominatim", return_value=[cand(-12.1, -77.03, "X"), cand(-12.2, -77.1, "Y")]) as nom:
            geocode.search_address("Mi Dirección 123")
            geocode.search_address("  mi dirección   123 ")
            self.assertEqual(nom.call_count, 1)
        geocode._cache.clear()
        with mock.patch.object(geocode, "_nominatim", side_effect=OSError("sin red")), mock.patch.object(geocode, "_photon", side_effect=OSError("sin red")):
            self.assertEqual(geocode.search_address("otra dirección"), [])
        self.assertNotIn("otra dirección", geocode._cache)                      # un corte de red no se recuerda como «no existe»

    def test_empty_query_and_limit(self):
        self.assertEqual(geocode.search_address("   "), [])
        many = [cand(-12.0 - i / 10, -77.0, f"n{i}") for i in range(8)]
        with mock.patch.object(geocode, "_nominatim", return_value=many), mock.patch.object(geocode, "_photon", return_value=[]):
            self.assertEqual(len(geocode.search_address("muchos", limit=3)), 3)


class ParseTests(unittest.TestCase):
    def test_google_maps_links_and_coordinates_still_work(self):
        self.assertEqual(geocode.parse_coordinates("-12.00989, -76.98364")["lat"], -12.00989)
        link = "https://www.google.com/maps/place/Jockey+Plaza/@-12.0846,-76.9753,17z/data=!3d-12.0850!4d-76.9750"
        point = geocode.parse_coordinates(link)
        self.assertAlmostEqual(point["lat"], -12.0846)
        self.assertIsNone(geocode.parse_coordinates("Av. Arequipa 100"))


if __name__ == "__main__":
    unittest.main()
