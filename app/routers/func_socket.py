
import logging
from fastapi import HTTPException, status
from app import models, schemas
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc
from typing import List


# Налаштування логування
logging.basicConfig(filename='log/func_vote.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)







async def fetch_last_messages(rooms: str, session: AsyncSession) -> List[schemas.SocketModel]:
    query = select(
        models.Socket, 
        models.User, 
        func.coalesce(func.sum(models.Vote.dir), 0).label('votes')
    ).outerjoin(
        models.Vote, models.Socket.id == models.Vote.message_id
    ).join(
        models.User, models.Socket.receiver_id == models.User.id
    ).filter(
        models.Socket.rooms == rooms
    ).group_by(
        models.Socket.id, models.User.id
    ).order_by(
        desc(models.Socket.created_at)
    ).limit(50)

    result = await session.execute(query)
    raw_messages = result.all()

    # Convert raw messages to SocketModel
    messages = [
        schemas.SocketModel(
            created_at=socket.created_at,
            receiver_id=socket.receiver_id,
            message=socket.message,
            user_name=user.user_name,
            avatar=user.avatar,
            verified=user.verified,
            id=socket.id,
            vote=votes, # Додавання кількості голосів
            id_return=socket.id_return
        )
        for socket, user, votes in raw_messages
    ]
    messages.reverse()
    return messages




async def update_room_for_user(user_id: int, room: str, session: AsyncSession):
    try:
        post_query = select(models.User_Status).where(models.User_Status.user_id == user_id)
        post_result = await session.execute(post_query)
        post = post_result.scalar()

        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User status with user_id: {user_id} not found"
            )

        post.name_room = room  # Оновлення поля з назвою кімнати
        await session.commit()

        return post
    except Exception as e:
        logging.error(f"Update user failed with error {e}")
        logging.error(f"Error updating user status: {e}")
        raise
    
    
async def update_room_for_user_live(user_id: int, session: AsyncSession):
    try:
        post_query = select(models.User_Status).where(models.User_Status.user_id == user_id)
        post_result = await session.execute(post_query)
        post = post_result.scalar()

        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User status with user_id: {user_id} not found"
            )

        post.name_room = 'Hell'  # Оновлення поля з назвою кімнати
        await session.commit()

        return post
    except Exception as e:
        logging.error(f"Error updating user status: {e}")
        raise



async def process_vote(vote: schemas.Vote, session: AsyncSession, current_user: models.User):
    try:
        # Виконання запиту і отримання першого результату
        result = await session.execute(select(models.Socket).filter(models.Socket.id == vote.message_id))
        message = result.scalars().first()
        
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Message with id: {vote.message_id} does not exist")
        
        # Перевірка наявності голосу
        vote_result = await session.execute(select(models.Vote).filter(
            models.Vote.message_id == vote.message_id, 
            models.Vote.user_id == current_user.id
        ))
        found_vote = vote_result.scalars().first()
        
        if vote.dir == 1:
            if found_vote:
                return {"message": f"User {current_user.id} has already voted on post {vote.message_id}"}
                
            new_vote = models.Vote(message_id=vote.message_id, user_id=current_user.id, dir=vote.dir)
            session.add(new_vote)
            await session.commit()
            return {"message": "Successfully added vote"}

        else:
            if not found_vote:
                return {"message": "Vote does not exist or has already been removed"}
            
            await session.delete(found_vote)
            await session.commit()
            
            return {"message" : "Successfully deleted vote"}

    except HTTPException as http_exc:
        # Логування помилки
        logging.error(f"HTTP error occurred: {http_exc.detail}")
        # Перекидання помилки далі
        raise http_exc
    except Exception as e:
        # Логування неочікуваних помилок
        logging.error(f"Unexpected error: {e}", exc_info=True)
        # Відправлення загального повідомлення про помилку
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An unexpected error occurred")