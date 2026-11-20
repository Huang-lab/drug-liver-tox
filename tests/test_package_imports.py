"""The package must import, and config's module-level tables must build.

`config.py` once carried `from turtle import pd`.
`turtle.pd` is turtle's pen-down function, so importing the module raised
`AttributeError: 'function' object has no attribute 'DataFrame'`.
`tests/test_sql_runner.py` loads `config.py` by file path, so that one line turned the whole
suite red while no test imported the package itself.
"""

import importlib

import pandas as pd


def test_package_imports_and_exports_resolve():
    pkg = importlib.import_module("drug_liver_toxicity")
    for name in pkg.__all__:
        assert hasattr(pkg, name), name


def test_measurement_units_table_has_one_unit_per_row():
    config = importlib.import_module("drug_liver_toxicity.config")
    df = config.MEASUREMENT_UNITS_DF
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["lab_name", "unit_name"]
    assert set(df["lab_name"]) == set(config.NEASUREMENT_UNITS)
    assert all(isinstance(unit, str) for unit in df["unit_name"])
    assert len(df) == sum(len(units) for units in config.NEASUREMENT_UNITS.values())
