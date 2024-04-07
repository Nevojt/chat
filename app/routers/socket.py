from datetime import datetime
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.settings.connection_manager import ConnectionManager
from app.settings.database import get_async_session
from app.settings import oauth2
from ..schemas import schemas
from sqlalchemy.ext.asyncio import AsyncSession

from app.functions.func_socket import update_user_status, change_message, fetch_last_messages, update_room_for_user, update_room_for_user_live, process_vote, delete_message
from app.functions.moderator import censor_message, load_banned_words

banned_words = load_banned_words("app/functions/banned_words.csv")

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Chat"]
)

manager = ConnectionManager()


@router.websocket("/test_chat/{room}")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str,
    token: str,
    session: AsyncSession = Depends(get_async_session)
    ):
    
    user = await oauth2.get_current_user(token, session)

    await manager.connect(websocket, user.id, user.user_name, user.avatar, room, user.verified)
    
      
    await update_room_for_user(user.id, room, session)
    
    x_real_ip = websocket.headers.get('x-real-ip')
    x_forwarded_for = websocket.headers.get('x-forwarded-for')

    # Використання отриманих IP-адрес
    print(f"X-Real-IP: {x_real_ip}")
    print(f"X-Forwarded-For: {x_forwarded_for}")
    
    await manager.send_active_users(room)
    
    # Отримуємо останні повідомлення
    messages = await fetch_last_messages(room, session)
    await update_user_status(session, user.id, True)
    # Відправляємо кожне повідомлення користувачеві
    for message in messages:  
        await websocket.send_text(message.model_dump_json()) 
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Created likes
            if 'vote' in data:
                try:
                    vote_data = schemas.Vote(**data['vote'])
                    await process_vote(vote_data, session, user)
                 
                    messages = await fetch_last_messages(room, session)
                    
                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_json({"message": "Vote posted "})
                        if user_room == room:
                            for message in messages:
                                await connection.send_text(message.model_dump_json())
                                

                except Exception as e:
                    logger.error(f"Error processing vote: {e}", exc_info=True)
                    await websocket.send_json({"message": f"Error processing vote: {e}"})
                    
            # Block change message 
            elif 'change_message' in data:
                try:
                    message_data = schemas.SocketUpdate(**data['change_message'])
                    
                    censored_text = censor_message(message_data.message, banned_words)
                    await change_message(message_data.id, schemas.SocketUpdate(id=message_data.id, message=censored_text), session, user)
                    
                    messages = await fetch_last_messages(room, session)
                    
                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_json({"message": "Message updated "})
                        if user_room == room:
                            for message in messages:
                                await connection.send_text(message.model_dump_json())
                                
                except Exception as e:
                    logger.error(f"Error processing change: {e}", exc_info=True)
                    await websocket.send_json({"message": f"Error processing change: {e}"})
            
            # Block delete message       
            elif 'delete_message' in data:
                try:
                    message_data = schemas.SocketDelete(**data['delete_message'])
                    await delete_message(message_data.id, session, user)
                    
                    messages = await fetch_last_messages(room, session)
                    
                    for user_id, (connection, _, _, user_room, _) in manager.user_connections.items():
                        await connection.send_json({"message": "Message delete"})
                        if user_room == room:
                            for message in messages:
                                await connection.send_text(message.model_dump_json())
                                
                except Exception as e:
                    logger.error(f"Error processing delete: {e}", exc_info=True)
                    await websocket.send_json({"message": f"Error processing deleted: {e}"})
                    
            # Block reply message     
            elif 'send' in data:
                message_data = data['send']
                original_message_id = message_data['original_message_id']
                original_message = message_data['message']
                file_url = message_data['fileUrl']
                
                if original_message != None:
                    censored_message = censor_message(original_message, banned_words)
                else:
                    censored_message = None
                
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if censored_message != original_message:
                    warning_message = {
                        "type": "system_warning",
                        "content": "Ваше повідомлення було модифіковано, оскільки воно містило нецензурні слова."
                    }  
                    await websocket.send_json(warning_message)
                await manager.broadcast(
                                    message=censored_message,
                                    file=file_url,
                                    rooms=room,
                                    created_at=current_time,
                                    receiver_id=user.id,
                                    user_name=user.user_name,
                                    avatar=user.avatar,
                                    verified=user.verified,
                                    id_return=original_message_id,
                                    add_to_db=True)

                
            # Blok following typing message
            elif 'type' in data:   
                await manager.notify_users_typing(room, user.user_name, user.id)
                
            
    except WebSocketDisconnect:
        print("Couldn't connect to")
        await update_user_status(session, user.id, False)
        await update_room_for_user(user.id, 'Hell', session)
        manager.disconnect(websocket, user.id)
        await update_room_for_user_live(user.id, session)
        
        await manager.send_active_users(room)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await websocket.send_text(f"User -> {user.user_name} left the chat {room}")
                                
    finally:
        await session.close()
        print("Session closed")