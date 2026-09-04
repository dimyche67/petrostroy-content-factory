from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import Rubric, RubricCode, Trend, TrendStatus, User, UserRole

RUBRICS_DATA = [
    {
        "code": RubricCode.video_clip,
        "emoji": "🎬",
        "name": "Видео-клип",
        "description": "15-60 сек с объекта: деталь, процесс",
        "trigger_audience": "Любопытство",
        "cta_template": "Угадайте, для чего это?",
        "frequency_hint": "2×/нед",
        "generation_prompt": (
            "Короткая подпись (3-5 предложений) к видео. Факты: {facts}. "
            "Интрига/вопрос. 3-5 хештегов. До 500 знаков."
        ),
        "min_chars": 200,
        "max_chars": 500,
    },
    {
        "code": RubricCode.layout,
        "emoji": "📐",
        "name": "Планировка",
        "description": "Разбор планировки: зоны, фишки",
        "trigger_audience": "«Хочу представить свой дом»",
        "cta_template": "А вы бы жили в таком?",
        "frequency_hint": "1×/нед",
        "generation_prompt": (
            "Разбор планировки. {facts}. Зонирование, фишки, для какой семьи. "
            "Финал «а вы бы жили?». 800-1200 знаков."
        ),
        "min_chars": 800,
        "max_chars": 1200,
    },
    {
        "code": RubricCode.horror,
        "emoji": "😱",
        "name": "Страшилка",
        "description": "Разбор чужой ошибки + как избежать",
        "trigger_audience": "Страх потери",
        "cta_template": "Сохраните, чтобы не повторить",
        "frequency_hint": "2×/мес",
        "generation_prompt": (
            "Предупреждение. {facts}. Структура: что пошло не так → почему → "
            "как избежать → как делает Петрострой. Серьёзно, без запугивания. 800-1500."
        ),
        "min_chars": 800,
        "max_chars": 1500,
    },
    {
        "code": RubricCode.done,
        "emoji": "🏠",
        "name": "Дом сдан",
        "description": "Кейс готового объекта, до/после",
        "trigger_audience": "Доверие / результат",
        "cta_template": "Хотите такой же? Рассчитаем",
        "frequency_hint": "По сдаче",
        "generation_prompt": (
            "Кейс. {facts}. Локация+площадь → сроки → было/стало → слова хозяина. "
            "Тёпло. CTA: рассчитать. 600-1000."
        ),
        "min_chars": 600,
        "max_chars": 1000,
    },
    {
        "code": RubricCode.expertise,
        "emoji": "🔧",
        "name": "Экспертиза",
        "description": "Техразбор: котельная, утепление",
        "trigger_audience": "«Они разбираются»",
        "cta_template": "Подписывайтесь — честно о стройке",
        "frequency_hint": "2×/мес",
        "generation_prompt": (
            "Экспертный пост. {facts}. Простым языком: что, зачем, как влияет. "
            "1 цифра. CTA: подписаться. 800-1200."
        ),
        "min_chars": 800,
        "max_chars": 1200,
    },
    {
        "code": RubricCode.battle,
        "emoji": "⚔️",
        "name": "Баттл",
        "description": "Сравнение решений + голосование",
        "trigger_audience": "Азарт + экспертиза",
        "cta_template": "Газобетон или кирпич? Голосуйте в комментариях!",
        "frequency_hint": "1×/мес",
        "generation_prompt": (
            "Голосование. {facts}. Два варианта по 2-3 плюса. Голос эмодзи. "
            "Без мнения компании. 600-1000."
        ),
        "min_chars": 600,
        "max_chars": 1000,
    },
    {
        "code": RubricCode.lifehack,
        "emoji": "💡",
        "name": "Лайфхак",
        "description": "Один конкретный полезный совет",
        "trigger_audience": "Польза",
        "cta_template": "Сохраните себе!",
        "frequency_hint": "1×/нед",
        "generation_prompt": (
            "Один совет. {facts}. Проблема → решение → выгода (цифра). "
            "CTA: сохранить. 400-700."
        ),
        "min_chars": 400,
        "max_chars": 700,
    },
    {
        "code": RubricCode.team,
        "emoji": "👷",
        "name": "Команда",
        "description": "Знакомство с прорабом/инженером",
        "trigger_audience": "Очеловечивание",
        "cta_template": "Это [Имя], он построил N домов",
        "frequency_hint": "2×/мес",
        "generation_prompt": (
            "Знакомство с человеком. {facts}. Что делает, стаж, что любит. "
            "Живо, уважительно. 500-800."
        ),
        "min_chars": 500,
        "max_chars": 800,
    },
    {
        "code": RubricCode.status,
        "emoji": "🏆",
        "name": "Статус",
        "description": "Партнёрство, аккредитация, юбилей",
        "trigger_audience": "Надёжность",
        "cta_template": "Петрострой — 400+ домов за 23 года",
        "frequency_hint": "По факту",
        "generation_prompt": (
            "Достижение. {facts}. Уверенно без хвастовства. "
            "Что это даёт клиенту. CTA: доверяйте проверенным. 400-600."
        ),
        "min_chars": 400,
        "max_chars": 600,
    },
]

TRENDS_DATA = [
    {
        "code": "#001",
        "source_competitor": "GOOD WOOD",
        "original_topic": "Короткое видео с деталью объекта + загадка",
        "er_original": 39.1,
        "rubric": RubricCode.video_clip,
        "trigger_text": "Любопытство",
        "adaptation_note": (
            "Снять 15-30 сек: деталь фундамента/кладки/крыши. «Угадайте, зачем это?»"
        ),
    },
    {
        "code": "#002",
        "source_competitor": "GOOD WOOD",
        "original_topic": "Планировка + «а вы бы жили?»",
        "er_original": 31.8,
        "rubric": RubricCode.layout,
        "trigger_text": "«Хочу представить свой дом»",
        "adaptation_note": "Показать планировку текущего проекта, спросить мнение",
    },
    {
        "code": "#003",
        "source_competitor": "GOOD WOOD",
        "original_topic": "Въездная группа — детали + загадка",
        "er_original": 12.9,
        "rubric": RubricCode.video_clip,
        "trigger_text": "Любопытство",
        "adaptation_note": "Готовый элемент: крыльцо, навес, ворота — «для чего эта деталь?»",
    },
    {
        "code": "#004",
        "source_competitor": "GOOD WOOD",
        "original_topic": "Мастер-спальня — обзор + «сделали бы так?»",
        "er_original": 11.6,
        "rubric": RubricCode.layout,
        "trigger_text": "«Хочу представить свой дом»",
        "adaptation_note": "Комната в готовом доме + вопрос аудитории",
    },
    {
        "code": "#005",
        "source_competitor": "Избург",
        "original_topic": "Баттл «Газобетон VS Каркас»",
        "er_original": 11.5,
        "rubric": RubricCode.battle,
        "trigger_text": "Азарт + экспертиза",
        "adaptation_note": "Голосование vs в комментариях",
    },
    {
        "code": "#006",
        "source_competitor": "Избург",
        "original_topic": "Газовая котельная — техразбор",
        "er_original": 8.6,
        "rubric": RubricCode.expertise,
        "trigger_text": "«Они разбираются»",
        "adaptation_note": "Инженерное решение с объекта Петростроя",
    },
    {
        "code": "#007",
        "source_competitor": "Избург",
        "original_topic": "«Сколько стоит забытый свет»",
        "er_original": 7.5,
        "rubric": RubricCode.lifehack,
        "trigger_text": "Польза",
        "adaptation_note": "Конкретная цифра + совет = экономия",
    },
    {
        "code": "#008",
        "source_competitor": "Династия",
        "original_topic": "«Сделка закрыта! Ключи!»",
        "er_original": 3.0,
        "rubric": RubricCode.done,
        "trigger_text": "Доверие / результат",
        "adaptation_note": "Каждая сдача = пост «Дом №N сдан!»",
    },
    {
        "code": "#009",
        "source_competitor": "Династия",
        "original_topic": "Партнёрство с банком",
        "er_original": 2.9,
        "rubric": RubricCode.status,
        "trigger_text": "Надёжность",
        "adaptation_note": "Аккредитация в Сбере / ДОМ.РФ",
    },
]


async def seed_rubrics(session: AsyncSession) -> None:
    for data in RUBRICS_DATA:
        existing = await session.scalar(
            select(Rubric).where(Rubric.code == data["code"])
        )
        if not existing:
            session.add(Rubric(**data))


async def seed_trends(session: AsyncSession) -> None:
    for data in TRENDS_DATA:
        existing = await session.scalar(select(Trend).where(Trend.code == data["code"]))
        if not existing:
            session.add(Trend(**data, status=TrendStatus.unused))


async def seed_users(session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.initial_users.strip():
        return

    for entry in settings.initial_users.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3:
            continue
        telegram_id, role_str, full_name = parts
        role = UserRole(role_str.strip())
        tid = int(telegram_id.strip())
        existing = await session.scalar(select(User).where(User.telegram_id == tid))
        if not existing:
            session.add(
                User(
                    telegram_id=tid,
                    full_name=full_name.strip(),
                    role=role,
                )
            )


async def seed_all(session: AsyncSession) -> None:
    await seed_rubrics(session)
    await seed_trends(session)
    await seed_users(session)
    await session.commit()
