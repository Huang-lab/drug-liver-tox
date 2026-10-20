import pandas as pd

df = pd.DataFrame(
    {
        "first_alt_event_date": [pd.NaT, "2024-01-10"],
        "first_ast_event_date": ["2024-01-13", pd.NaT],
        "first_bili_event_date": [pd.NaT, pd.NaT],
        "first_alp_event_date": ["2024-01-12", pd.NaT],
    }
)

print(df.bfill(axis=1).iloc[:, 0])
