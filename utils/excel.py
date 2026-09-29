"""Lectura/escritura de Excel para importar y exportar catálogos."""
from __future__ import annotations

import io

import pandas as pd


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def read_excel_upload(uploaded_file) -> pd.DataFrame:
    return pd.read_excel(uploaded_file, dtype=str).convert_dtypes()
