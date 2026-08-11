from pathlib import Path

import pandas as pd
import uvicorn

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from auth import authenticate_user, create_access_token, get_current_user, require_admin


app = FastAPI(
    title="Pinewood Senior Living API"
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GOLD_FACT_DIR = PROJECT_ROOT / "data" / "gold" / "fact"


@app.get("/")
def home():

    return {
        "message": "Pinewood Senior Living API is running"
    }


@app.post("/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    # Check username and password
    user = authenticate_user(
        form_data.username,
        form_data.password
    )

    # If username/password is wrong
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    # Create JWT token
    token = create_access_token(
        username=user["username"],
        role=user["role"]
    )

    # Return token to user
    return {
        "access_token": token,
        "token_type": "bearer"
    }


@app.get("/incidents")
def get_incidents(
    current_user=Depends(get_current_user)
):

    incidents_df = pd.read_parquet(
        GOLD_FACT_DIR / "fact_incidents.parquet"
    )

    return incidents_df.to_dict(
        orient="records"
    )


@app.get("/carehistory")
def get_carehistory(
    current_user=Depends(require_admin)
):

    carehistory_df = pd.read_parquet(
        GOLD_FACT_DIR / "fact_care_history.parquet"
    )

    return carehistory_df.to_dict(
        orient="records"
    )


if __name__ == "__main__":

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )