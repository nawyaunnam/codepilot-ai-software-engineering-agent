from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,ForeignKey,Integer,String,Text,create_engine
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column,sessionmaker
from .config import settings
class Base(DeclarativeBase):pass
class Repository(Base):
    __tablename__="repositories";id:Mapped[int]=mapped_column(primary_key=True);name:Mapped[str]=mapped_column(String(200));root_path:Mapped[str]=mapped_column(Text);status:Mapped[str]=mapped_column(String(30),default="pending");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class CodeChunk(Base):
    __tablename__="code_chunks";id:Mapped[int]=mapped_column(primary_key=True);repository_id:Mapped[int]=mapped_column(ForeignKey("repositories.id"),index=True);path:Mapped[str]=mapped_column(Text,index=True);language:Mapped[str]=mapped_column(String(30));symbol:Mapped[str]=mapped_column(String(300),index=True);kind:Mapped[str]=mapped_column(String(40));start_line:Mapped[int]=mapped_column(Integer);end_line:Mapped[int]=mapped_column(Integer);content:Mapped[str]=mapped_column(Text);search_text:Mapped[str]=mapped_column(Text);metadata_json:Mapped[dict]=mapped_column(JSON,default=dict)
class Dependency(Base):
    __tablename__="dependencies";id:Mapped[int]=mapped_column(primary_key=True);repository_id:Mapped[int]=mapped_column(ForeignKey("repositories.id"),index=True);source_path:Mapped[str]=mapped_column(Text,index=True);target:Mapped[str]=mapped_column(Text,index=True);kind:Mapped[str]=mapped_column(String(30));line:Mapped[int]=mapped_column(Integer)
args={"check_same_thread":False} if settings.database_url.startswith("sqlite") else {}
engine=create_engine(settings.database_url,connect_args=args,pool_pre_ping=True);SessionLocal=sessionmaker(engine,expire_on_commit=False)
def init_db():Base.metadata.create_all(engine)

