from fastapi import FastAPI

app= FastAPI()


@app.get("/ahmed")
def read_root():
    return {"Hello": "World rahma  and amine gbh"}     