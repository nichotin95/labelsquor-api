"""
Base repository pattern implementation with async support
"""
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Union
from uuid import UUID
from datetime import datetime
from abc import ABC, abstractmethod

from sqlmodel import SQLModel, select, func, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import asc, desc
from pydantic import BaseModel

from app.core.logging import log
from app.core.exceptions import NotFoundError, ConflictError, DatabaseError


ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], ABC):
    """
    Generic repository for data access with async support.
    Implements common CRUD operations.
    """
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def create(self, *, obj_in: CreateSchemaType, **kwargs) -> ModelType:
        """Create a new record"""
        try:
            # Convert Pydantic model to dict
            obj_in_data = obj_in.model_dump(exclude_unset=True)
            obj_in_data.update(kwargs)  # Add any additional fields
            
            # Create SQLModel instance
            db_obj = self.model(**obj_in_data)
            
            self.session.add(db_obj)
            await self.session.commit()
            await self.session.refresh(db_obj)
            
            log.info(f"Created {self.model.__name__}", id=str(db_obj.id))
            return db_obj
            
        except IntegrityError as e:
            await self.session.rollback()
            log.error(f"Integrity error creating {self.model.__name__}", error=str(e))
            raise ConflictError(f"Conflict creating {self.model.__name__}")
        except SQLAlchemyError as e:
            await self.session.rollback()
            log.error(f"Database error creating {self.model.__name__}", error=str(e))
            raise DatabaseError(f"Error creating {self.model.__name__}")
    
    async def get(self, *, id: Union[UUID, str]) -> Optional[ModelType]:
        """Get a record by ID"""
        if isinstance(id, str):
            id = UUID(id)
        
        statement = select(self.model).where(self.model.id == id)
        result = await self.session.exec(statement)
        return result.first()
    
    async def get_or_404(self, *, id: Union[UUID, str]) -> ModelType:
        """Get a record by ID or raise NotFoundError"""
        obj = await self.get(id=id)
        if not obj:
            raise NotFoundError(f"{self.model.__name__} not found")
        return obj
    
    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple records with pagination and filtering"""
        statement = select(self.model)
        
        # Apply filters
        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        conditions.append(getattr(self.model, field).in_(value))
                    else:
                        conditions.append(getattr(self.model, field) == value)
            if conditions:
                statement = statement.where(and_(*conditions))
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            statement = statement.order_by(desc(order_column) if order_desc else asc(order_column))
        
        # Apply pagination
        statement = statement.offset(skip).limit(limit)
        
        result = await self.session.exec(statement)
        return result.all()
    
    async def count(self, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering"""
        statement = select(func.count()).select_from(self.model)
        
        # Apply filters
        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        conditions.append(getattr(self.model, field).in_(value))
                    else:
                        conditions.append(getattr(self.model, field) == value)
            if conditions:
                statement = statement.where(and_(*conditions))
        
        result = await self.session.exec(statement)
        return result.one()
    
    async def update(
        self,
        *,
        id: Union[UUID, str],
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """Update a record"""
        try:
            db_obj = await self.get_or_404(id=id)
            
            # Convert to dict if it's a Pydantic model
            if isinstance(obj_in, BaseModel):
                update_data = obj_in.model_dump(exclude_unset=True)
            else:
                update_data = obj_in
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            # Update timestamp if model has it
            if hasattr(db_obj, "updated_at"):
                db_obj.updated_at = datetime.utcnow()
            
            self.session.add(db_obj)
            await self.session.commit()
            await self.session.refresh(db_obj)
            
            log.info(f"Updated {self.model.__name__}", id=str(id))
            return db_obj
            
        except IntegrityError as e:
            await self.session.rollback()
            log.error(f"Integrity error updating {self.model.__name__}", error=str(e))
            raise ConflictError(f"Conflict updating {self.model.__name__}")
        except SQLAlchemyError as e:
            await self.session.rollback()
            log.error(f"Database error updating {self.model.__name__}", error=str(e))
            raise DatabaseError(f"Error updating {self.model.__name__}")
    
    async def delete(self, *, id: Union[UUID, str]) -> bool:
        """Delete a record (soft delete if supported)"""
        try:
            db_obj = await self.get_or_404(id=id)
            
            # Check if model supports soft delete
            if hasattr(db_obj, "deleted_at"):
                db_obj.deleted_at = datetime.utcnow()
                self.session.add(db_obj)
            else:
                await self.session.delete(db_obj)
            
            await self.session.commit()
            
            log.info(f"Deleted {self.model.__name__}", id=str(id))
            return True
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            log.error(f"Database error deleting {self.model.__name__}", error=str(e))
            raise DatabaseError(f"Error deleting {self.model.__name__}")
    
    async def exists(self, *, id: Union[UUID, str]) -> bool:
        """Check if a record exists"""
        if isinstance(id, str):
            id = UUID(id)
        
        statement = select(func.count()).select_from(self.model).where(self.model.id == id)
        result = await self.session.exec(statement)
        return result.one() > 0
    
    async def bulk_create(self, *, objects_in: List[CreateSchemaType]) -> List[ModelType]:
        """Bulk create multiple records"""
        try:
            db_objects = []
            for obj_in in objects_in:
                obj_in_data = obj_in.model_dump(exclude_unset=True)
                db_objects.append(self.model(**obj_in_data))
            
            self.session.add_all(db_objects)
            await self.session.commit()
            
            # Refresh all objects
            for db_obj in db_objects:
                await self.session.refresh(db_obj)
            
            log.info(f"Bulk created {len(db_objects)} {self.model.__name__} records")
            return db_objects
            
        except IntegrityError as e:
            await self.session.rollback()
            log.error(f"Integrity error bulk creating {self.model.__name__}", error=str(e))
            raise ConflictError(f"Conflict bulk creating {self.model.__name__}")
        except SQLAlchemyError as e:
            await self.session.rollback()
            log.error(f"Database error bulk creating {self.model.__name__}", error=str(e))
            raise DatabaseError(f"Error bulk creating {self.model.__name__}")
