from fastapi import FastAPI

app= FastAPI()


@app.get("/ahmeddd")
def read_root():
    return {"Hello": "World rahma  and amine gbh"}     