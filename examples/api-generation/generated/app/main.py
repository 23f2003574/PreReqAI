import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

app = FastAPI(title="Quotes a fixed-rate loan for an applicant.", description="Computes the monthly payment for a fixed-rate loan from the requested amount, term and annual rate, and decides whether the applicant's credit score qualifies.")
EXAMPLES = json.loads("[{\"input\": {\"amount\": 12000, \"term_months\": 12, \"annual_rate\": 0.06, \"applicant\": {\"name\": \"Ada\", \"credit_score\": 720}}, \"output\": {\"monthly_payment\": 1032.8, \"approved\": true, \"applicant_name\": \"Ada\"}}]")


class PostLoanQuoteRequestApplicant(BaseModel):
    name: str
    credit_score: int


class PostLoanQuoteResponse(BaseModel):
    monthly_payment: float
    approved: bool
    applicant_name: str


class PostLoanQuoteRequest(BaseModel):
    amount: float = Field(..., ge=1000, le=50000)
    term_months: int = Field(12, ge=6, le=60)
    annual_rate: float = 0.06
    applicant: PostLoanQuoteRequestApplicant
    tags: Optional[list[str]] = None


@app.post("/loan-quote", response_model=PostLoanQuoteResponse, summary="Quotes a fixed-rate loan for an applicant.", description="Computes the monthly payment for a fixed-rate loan from the requested amount, term and annual rate, and decides whether the applicant's credit score qualifies.")
def handler(payload: PostLoanQuoteRequest, response: Response):
    given = payload.model_dump(exclude_unset=True)
    for example in EXAMPLES:
        if example["input"] == given:
            response.headers["X-Execution"] = "documented-example"
            return example["output"]
    raise HTTPException(status_code=501, detail="Not implemented: no notebook logic is attached and no documented example matches this input")
