from src.app.core.security import hash_password, verify_password, create_access_token
from src.app.domain.contracts.uow import UoW

class AuthService:
    def __init__(self, uow: UoW):
        self.uow = uow

    def register(self, email: str, password: str, account_name: str) -> str:
        try:
            # Проверка на существование пользователя
            if self.uow.users.get_by_email(email):
                raise ValueError("Пользователь уже существует.")

            # Валидация пароля
            if len(password.encode("utf-8")) > 72:
                raise ValueError("Пароль должен быть не длиннее 72 байт.")

            # Создаём пользователя
            user = self.uow.users.create(
                email=email,
                password_hash=hash_password(password),
            )

            # Создаём аккаунт
            account_id = self.uow.accounts.create(name=account_name)

            # Привязываем пользователя к аккаунту
            self.uow.accounts.add_user(
                account_id=account_id,
                user_id=user.id,
                role="owner",
            )

            # Создаём подписку (free)
            self.uow.subscriptions.ensure_free_active(account_id)

            # выдаём доступ к глобальным sources
            self.uow.account_sources.grant_all_global(account_id)

            # Коммит транзакции
            self.uow.commit()

            # Возвращаем токен
            return create_access_token(
                subject=str(user.id),
                extra={"account_id": account_id},
            )

        except Exception:
            self.uow.rollback()
            raise

    def login(self, email: str, password: str) -> str:
        creds = self.uow.users.get_auth_credentials(email)
        if not creds or not verify_password(password, creds.password_hash):
            raise ValueError("Неверные учетные данные.")

        link = self.uow.accounts.get_user_link(creds.user_id)
        if not link:
            raise ValueError("У пользователя нет аккаунта.")

        account_id, _role = link

        return create_access_token(
            subject=str(creds.user_id),
            extra={"account_id": account_id},
        )