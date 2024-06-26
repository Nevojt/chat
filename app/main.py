
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat_socket


app = FastAPI(
    docs_url="/docs",
    title="Chat",
    version="0.1.0",
    description="Chat API",
    
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_socket.router)
