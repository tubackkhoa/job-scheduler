from typing import Optional
from .model import Base, engine, SessionLocal, Post

Base.metadata.create_all(bind=engine)


def get_posts(limit: Optional[int] = None):
    db = SessionLocal()
    query = db.query(Post.id, Post.title, Post.description).order_by(Post.id.desc())

    if limit is not None:
        query = query.limit(limit)

    ret = query.all()
    db.close()
    return ret


def create_post(title: str, description: str, content: str):
    db = SessionLocal()
    if not title:
        db.close()
        raise ValueError("Title is required")
    post = Post(title=title, description=description, content=content)
    db.add(post)
    db.commit()
    db.refresh(post)
    db.close()
    return post


def update_post(post_id: int, title=None, description=None, content=None):
    db = SessionLocal()
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        db.close()
        return None

    if title is not None:
        post.title = title
    if description is not None:
        post.description = description
    if content is not None:
        post.content = content

    db.commit()
    db.refresh(post)
    db.close()
    return post


def delete_post(post_id: int):
    db = SessionLocal()

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        db.close()
        return False

    db.delete(post)
    db.commit()
    db.close()
    return True


def get_post(post_id: int):
    db = SessionLocal()
    post = db.query(Post).filter(Post.id == post_id).first()
    db.close()
    if not post:
        return None

    return {
        "id": post.id,
        "title": post.title,
        "description": post.description,
        "content": post.content,
    }
