from app.routes import rooms, chat

app.include_router(rooms.router)
app.include_router(chat.router)
