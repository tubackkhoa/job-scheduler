from typing import Optional

from sqlalchemy import select
from enforcer import job_permission
from .models import session_factory, Post


async def get_posts(limit: Optional[int] = None):
    async with session_factory() as session:
        stmt = select(Post.id, Post.title, Post.description).order_by(Post.id.desc())

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        return result.all()


@job_permission("blog")
async def create_post(ctx, title: str, description: str, content: str):
    if not title:
        raise ValueError("Title is required")

    async with session_factory() as session:
        post = Post(title=title, description=description, content=content)

        session.add(post)
        await session.commit()
        await session.refresh(post)

        return post


@job_permission("blog")
async def update_post(ctx, post_id: int, title=None, description=None, content=None):
    async with session_factory() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            return None

        if title is not None:
            post.title = title
        if description is not None:
            post.description = description
        if content is not None:
            post.content = content

        await session.commit()
        await session.refresh(post)

        return post


@job_permission("blog")
async def delete_post(ctx, post_id: int):
    async with session_factory() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            return False

        await session.delete(post)
        await session.commit()

        return True


async def get_post(post_id: int):
    async with session_factory() as session:
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            return None

        return {
            "id": post.id,
            "title": post.title,
            "description": post.description,
            "content": post.content,
        }
