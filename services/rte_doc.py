from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

app = FastAPI()

# Enums for consistent formatting values
class AlignmentType(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"

class ListType(str, Enum):
    BULLET = "bullet"
    NUMBER = "number"

class ElementType(str, Enum):
    DOCUMENT = "document"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TEXT = "text"
    SPAN = "span"
    LIST = "list"
    LIST_ITEM = "listItem"
    HYPERLINK = "hyperlink"
    LINE_BREAK = "lineBreak"

# Formatting models
class SpacingModel(BaseModel):
    before: int = Field(default=0, description="Space before in points")
    after: int = Field(default=0, description="Space after in points")
    line_spacing: float = Field(default=1.15, description="Line spacing multiplier")

class TextFormatting(BaseModel):
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    font_size: Optional[float] = Field(None, description="Font size in points")
    color: Optional[str] = Field(None, description="Text color in hex format")
    background_color: Optional[str] = Field(None, description="Background color in hex format")
    font_family: Optional[str] = None

class ParagraphFormatting(BaseModel):
    alignment: Optional[AlignmentType] = AlignmentType.LEFT
    spacing: Optional[SpacingModel] = None
    indent: Optional[int] = Field(None, description="Indent in twips (1440 twips = 1 inch)")

class ListFormatting(BaseModel):
    indent: int = Field(default=720, description="List indent in twips")
    bullet_style: Optional[str] = Field(None, description="Bullet style for bullet lists")
    number_style: Optional[str] = Field(None, description="Number style for numbered lists")

# Content element models
class RTFElement(BaseModel):
    type: ElementType
    content: Optional[Union[str, List['RTFElement']]] = None
    formatting: Optional[Dict[str, Any]] = None

class TextElement(RTFElement):
    type: ElementType = ElementType.TEXT
    content: str
    formatting: Optional[TextFormatting] = None

class ParagraphElement(RTFElement):
    type: ElementType = ElementType.PARAGRAPH
    content: List[RTFElement]
    formatting: Optional[ParagraphFormatting] = None

class HeadingElement(RTFElement):
    type: ElementType = ElementType.HEADING
    level: int = Field(..., ge=1, le=6, description="Heading level 1-6")
    content: List[RTFElement]
    formatting: Optional[TextFormatting] = None

class ListElement(RTFElement):
    type: ElementType = ElementType.LIST
    list_type: ListType
    content: List['ListItemElement']
    formatting: Optional[ListFormatting] = None

class ListItemElement(RTFElement):
    type: ElementType = ElementType.LIST_ITEM
    content: List[RTFElement]
    formatting: Optional[ParagraphFormatting] = None

class HyperlinkElement(RTFElement):
    type: ElementType = ElementType.HYPERLINK
    url: str
    content: List[RTFElement]
    formatting: Optional[TextFormatting] = None

class LineBreakElement(RTFElement):
    type: ElementType = ElementType.LINE_BREAK
    content: None = None
    formatting: None = None

class SpanElement(RTFElement):
    type: ElementType = ElementType.SPAN
    content: List[RTFElement]
    formatting: Optional[TextFormatting] = None

# Document metadata
class DocumentMetadata(BaseModel):
    created: datetime
    format: str = "rtf-word-compatible"
    author: Optional[str] = None
    title: Optional[str] = None

# Main document model
class RTFDocument(BaseModel):
    type: ElementType = ElementType.DOCUMENT
    content: List[RTFElement]
    metadata: DocumentMetadata

# API request models
class RTFContentRequest(BaseModel):
    rtf_data: RTFDocument
    document_id: str

class RTFContentResponse(BaseModel):
    success: bool
    message: str
    document_id: str
    word_xml_preview: Optional[str] = None

# Word XML conversion utilities
class WordXMLConverter:
    """Converts RTF data structure to Microsoft Word XML format"""
    
    @staticmethod
    def convert_to_word_xml(rtf_doc: RTFDocument) -> str:
        """Convert RTF document to Word XML"""
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
            '<w:body>'
        ]
        
        for element in rtf_doc.content:
            xml_parts.append(WordXMLConverter._convert_element(element))
        
        xml_parts.extend(['</w:body>', '</w:document>'])
        return '\n'.join(xml_parts)
    
    @staticmethod
    def _convert_element(element: RTFElement) -> str:
        """Convert individual RTF element to Word XML"""
        if element.type == ElementType.PARAGRAPH:
            return WordXMLConverter._convert_paragraph(element)
        elif element.type == ElementType.HEADING:
            return WordXMLConverter._convert_heading(element)
        elif element.type == ElementType.LIST:
            return WordXMLConverter._convert_list(element)
        elif element.type == ElementType.TEXT:
            return WordXMLConverter._convert_text(element)
        elif element.type == ElementType.HYPERLINK:
            return WordXMLConverter._convert_hyperlink(element)
        elif element.type == ElementType.LINE_BREAK:
            return '<w:br/>'
        else:
            # Handle other elements recursively
            if hasattr(element, 'content') and isinstance(element.content, list):
                return ''.join(WordXMLConverter._convert_element(child) for child in element.content)
            return ''
    
    @staticmethod
    def _convert_paragraph(element: ParagraphElement) -> str:
        """Convert paragraph to Word XML"""
        xml = ['<w:p>']
        
        # Add paragraph properties if present
        if element.formatting:
            xml.append('<w:pPr>')
            if element.formatting.alignment:
                xml.append(f'<w:jc w:val="{element.formatting.alignment.value}"/>')
            if element.formatting.spacing:
                spacing = element.formatting.spacing
                xml.append(f'<w:spacing w:before="{spacing.before * 20}" w:after="{spacing.after * 20}" w:line="{int(spacing.line_spacing * 240)}" w:lineRule="auto"/>')
            xml.append('</w:pPr>')
        
        # Add paragraph content
        for child in element.content:
            xml.append(WordXMLConverter._convert_element(child))
        
        xml.append('</w:p>')
        return ''.join(xml)
    
    @staticmethod
    def _convert_heading(element: HeadingElement) -> str:
        """Convert heading to Word XML"""
        xml = ['<w:p>']
        xml.append('<w:pPr>')
        xml.append(f'<w:pStyle w:val="Heading{element.level}"/>')
        xml.append('</w:pPr>')
        
        for child in element.content:
            xml.append(WordXMLConverter._convert_element(child))
        
        xml.append('</w:p>')
        return ''.join(xml)
    
    @staticmethod
    def _convert_text(element: TextElement) -> str:
        """Convert text to Word XML with formatting"""
        xml = ['<w:r>']
        
        # Add run properties if formatting is present
        if element.formatting:
            xml.append('<w:rPr>')
            fmt = element.formatting
            if fmt.bold:
                xml.append('<w:b/>')
            if fmt.italic:
                xml.append('<w:i/>')
            if fmt.underline:
                xml.append('<w:u w:val="single"/>')
            if fmt.font_size:
                xml.append(f'<w:sz w:val="{int(fmt.font_size * 2)}"/>')
            if fmt.color:
                xml.append(f'<w:color w:val="{fmt.color.lstrip("#")}"/>')
            if fmt.background_color:
                xml.append(f'<w:highlight w:val="{fmt.background_color.lstrip("#")}"/>')
            xml.append('</w:rPr>')
        
        xml.append(f'<w:t>{element.content}</w:t>')
        xml.append('</w:r>')
        return ''.join(xml)
    
    @staticmethod
    def _convert_hyperlink(element: HyperlinkElement) -> str:
        """Convert hyperlink to Word XML"""
        xml = [f'<w:hyperlink r:id="rId1" w:history="1">']
        
        for child in element.content:
            xml.append(WordXMLConverter._convert_element(child))
        
        xml.append('</w:hyperlink>')
        return ''.join(xml)
    
    @staticmethod
    def _convert_list(element: ListElement) -> str:
        """Convert list to Word XML"""
        xml = []
        for item in element.content:
            if item.type == ElementType.LIST_ITEM:
                xml.append('<w:p>')
                xml.append('<w:pPr>')
                xml.append('<w:numPr>')
                xml.append('<w:ilvl w:val="0"/>')
                xml.append('<w:numId w:val="1"/>')
                xml.append('</w:numPr>')
                xml.append('</w:pPr>')
                
                for child in item.content:
                    xml.append(WordXMLConverter._convert_element(child))
                
                xml.append('</w:p>')
        
        return ''.join(xml)

# API endpoints
@app.post("/api/document/rtf-content", response_model=RTFContentResponse)
async def save_rtf_content(request: RTFContentRequest):
    """
    Save RTF content and convert to Word XML format
    """
    try:
        # Validate the RTF data structure
        rtf_doc = request.rtf_data
        
        # Convert to Word XML
        word_xml = WordXMLConverter.convert_to_word_xml(rtf_doc)
        
        # Here you would typically save to database
        # await save_document_to_db(request.document_id, rtf_doc, word_xml)
        
        return RTFContentResponse(
            success=True,
            message="RTF content saved successfully",
            document_id=request.document_id,
            word_xml_preview=word_xml[:500] + "..." if len(word_xml) > 500 else word_xml
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing RTF content: {str(e)}")

@app.get("/api/document/{document_id}/rtf")
async def get_rtf_content(document_id: str):
    """
    Retrieve RTF content for a document
    """
    # Here you would typically fetch from database
    # rtf_data = await get_document_from_db(document_id)
    
    return {
        "document_id": document_id,
        "rtf_data": {
            "type": "document",
            "content": [],
            "metadata": {
                "created": datetime.now().isoformat(),
                "format": "rtf-word-compatible"
            }
        }
    }

@app.get("/api/document/{document_id}/word-xml")
async def get_word_xml(document_id: str):
    """
    Get Word XML representation of the document
    """
    # Here you would fetch RTF data and convert to Word XML
    # rtf_data = await get_document_from_db(document_id)
    # word_xml = WordXMLConverter.convert_to_word_xml(rtf_data)
    
    return {
        "document_id": document_id,
        "word_xml": "<?xml version='1.0' encoding='UTF-8'?>...",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }

# Update existing models to handle forward references
RTFElement.model_rebuild()
ParagraphElement.model_rebuild()
HeadingElement.model_rebuild()
ListElement.model_rebuild()
ListItemElement.model_rebuild()
HyperlinkElement.model_rebuild()
SpanElement.model_rebuild()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)