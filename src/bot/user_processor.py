from aiogram.types import Message
from db.models import User


class UserProcessor:
    @staticmethod
    def can_user_make_request(user: User) -> bool:
        if not user.username:
            return False, "Для використання бота необхідно встнановити юзернейм у налаштуваннях Telegram."
        if user.request_count >= user.daily_limit:
            return False, "Твій денний ліміт запитів вичерпано. Спробуй завтра або онови свій план."
        return True, None
    
    @staticmethod
    def get_user_id_from_message(message: Message) -> int:
        return message.from_user.id
    
    @staticmethod
    def create_user_from_message(message: Message) -> User:
        return User(
            user_id=message.from_user.id,
            username=message.from_user.username,
            role="user"
        )
    
    @staticmethod
    def get_username_from_message(message: Message) -> str | None:
        return message.from_user.username
    
    @staticmethod
    def update_user_username(user: User, message: Message) -> User:
        user.username = message.from_user.username
        return user
    
    @staticmethod
    def get_user_profile_text(user: User) -> str:
        profile = f"@{user.username}\n" if user.username else "Username: Не поставлено\n"
        profile += f"Роль: {user.role.value}\n"
        profile += f"Запитів сьогодні: {user.request_count}/{user.daily_limit}\n"
        profile += f"Запитів за весь час: {user.total_requests_lifetime}\n"
        profile += f"Перший запит: {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        profile += f"Останній запит: {user.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        return profile
