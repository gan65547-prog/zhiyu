#!/usr/bin/env python3
"""
测试 EPUB 文件解析功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from core.rag.document_processor import DocumentProcessor


async def test_epub_extraction(epub_path: str):
    """测试 EPUB 文本提取"""
    print(f"测试 EPUB 文件: {epub_path}")
    print("=" * 80)
    
    if not os.path.exists(epub_path):
        print(f"错误: 文件不存在 - {epub_path}")
        return
    
    processor = DocumentProcessor()
    
    print("开始提取文本...")
    text = await processor.extract_text(epub_path, "epub")
    
    print(f"\n提取结果:")
    print(f"- 文本长度: {len(text)} 字符")
    print(f"- 是否为空: {not text or not text.strip()}")
    
    if text:
        print("\n前 500 个字符预览:")
        print("-" * 80)
        print(text[:500])
        print("-" * 80)
        
        # 尝试分块
        chunks = processor.split_text(text)
        print(f"\n分块数量: {len(chunks)}")
        if chunks:
            print(f"第一块长度: {len(chunks[0])} 字符")
            print(f"最后一块长度: {len(chunks[-1])} 字符")


if __name__ == "__main__":
    import asyncio
    
    if len(sys.argv) < 2:
        print("用法: python test_epub_parser.py <epub文件路径>")
        print("示例: python test_epub_parser.py test.epub")
        sys.exit(1)
    
    epub_path = sys.argv[1]
    asyncio.run(test_epub_extraction(epub_path))
