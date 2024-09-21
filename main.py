from fastapi import FastAPI

from ovpn_helper import genrate_client

app = FastAPI()

@app.get("/genrate_user")
async def genrate_user():
    gen_user = genrate_user()
    result = gen_user.registor_client()

    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
