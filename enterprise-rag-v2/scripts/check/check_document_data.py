import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import Document, Dataset
from sqlalchemy import select, join

async def check_document_data():
    async with get_db_context() as session:
        # 检查文档数据
        result = await session.execute(
            select(Document, Dataset.name)
            .join(Dataset, Document.dataset_id == Dataset.id)
        )
        documents = result.all()
        
        print("文档数据:")
        if not documents:
            print("  暂无文档")
        else:
            for doc, dataset_name in documents:
                print(f"  文档: {doc.file_name} (ID: {doc.id})")
                print(f"    数据集: {dataset_name}")
                print(f"    状态: {doc.status}")
                print(f"    大小: {doc.file_size} bytes")
                print(f"    类型: {doc.file_type}")
                print()

if __name__ == "__main__":
    asyncio.run(check_document_data())