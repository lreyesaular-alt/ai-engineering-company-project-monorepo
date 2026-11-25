from io import BytesIO

import pandas as pd


VALID_LOCATIONS = {
    "COL-01",
    "COL-02",
    "COL-03",
    "COL-04",
    "COL-05",
    "COL-06",
    "COL-07",
    "COL-08",
    "COL-09",
    "COL-10",
    "FLA-01",
    "FLA-02",
    "FLA-03",
    "FLA-04",
}


VALID_CATEGORIES = {
    "CUSTOMER_COMPLAINT",
    "EQUIPMENT",
    "SUPPLY",
    "FOOD_QUALITY",
    "STAFF",
}


VALID_STATUSES = {
    "OPEN",
    "CLOSED",
    "DISCARDED",
}


REQUIRED_COLUMNS = {
    "location_id",
    "category",
    "description",
    "reporter_id",
    "status",
    "satisfaction_score",
}



def analyze_csv(contents: bytes):
    if not contents.strip():
        raise ValueError("El archivo est? vac?o.")

    df = pd.read_csv(BytesIO(contents))

    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Faltan columnas: {sorted(missing_columns)}"
        )

    location_values = (
        df["location_id"]
        .astype("string")
        .str.strip()
    )

    category_values = (
        df["category"]
        .astype("string")
        .str.strip()
    )

    description_values = (
        df["description"]
        .astype("string")
        .str.strip()
    )

    reporter_values = (
        df["reporter_id"]
        .astype("string")
        .str.strip()
    )

    status_values = (
        df["status"]
        .astype("string")
        .str.strip()
    )

    invalid_location = (
        location_values.isna()
        | ~location_values.isin(VALID_LOCATIONS)
    )

    invalid_category = (
        category_values.isna()
        | ~category_values.isin(VALID_CATEGORIES)
    )

    invalid_description = (
        description_values.isna()
        | (description_values.str.len() < 5)
    )

    invalid_reporter = (
        reporter_values.isna()
        | (reporter_values == "")
    )

    invalid_status = (
        status_values.isna()
        | ~status_values.isin(VALID_STATUSES)
    )

    score = pd.to_numeric(
        df["satisfaction_score"],
        errors="coerce",
    )

    missing_closed_score = (
        (status_values == "CLOSED")
        & score.isna()
    )

    invalid_score = (
        score.notna()
        & ~score.between(1, 5)
    )

    invalid_any = (
        invalid_location
        | invalid_category
        | invalid_description
        | invalid_reporter
        | invalid_status
        | missing_closed_score
        | invalid_score
    )

    valid_df = df[~invalid_any].copy()

    closed_df = valid_df[
        status_values[~invalid_any] == "CLOSED"
    ]

    closed_scores = pd.to_numeric(
        closed_df["satisfaction_score"],
        errors="coerce",
    )

    average_satisfaction = (
        round(
            float(closed_scores.mean()),
            2,
        )
        if not closed_scores.empty
        else None
    )

    return {
        "total_records": len(df),
        "valid_records": len(valid_df),
        "invalid_records": int(
            invalid_any.sum()
        ),
        "invalid_breakdown": {
            "invalid_location": int(
                invalid_location.sum()
            ),
            "invalid_category": int(
                invalid_category.sum()
            ),
            "invalid_description": int(
                invalid_description.sum()
            ),
            "invalid_reporter": int(
                invalid_reporter.sum()
            ),
            "invalid_status": int(
                invalid_status.sum()
            ),
            "missing_closed_score": int(
                missing_closed_score.sum()
            ),
            "invalid_score": int(
                invalid_score.sum()
            ),
        },
        "by_category": (
            valid_df["category"]
            .value_counts()
            .to_dict()
        ),
        "by_status": (
            valid_df["status"]
            .value_counts()
            .to_dict()
        ),
        "closed_incidents": len(closed_df),
        "average_satisfaction": average_satisfaction,
    }
