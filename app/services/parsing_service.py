"""
Parsing service for label extraction (placeholder)
"""
from app.core.logging import log


class ParsingService:
    """Service for parsing product labels"""
    
    async def parse_label_image(self, image_path: str) -> dict:
        """Parse label from image - to be implemented"""
        log.info("Label parsing not yet implemented")
        return {
            "status": "not_implemented",
            "message": "OCR and parsing coming soon"
        }
