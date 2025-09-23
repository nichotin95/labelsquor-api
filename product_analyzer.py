#!/usr/bin/env python3
"""
Unified Product Analyzer - All functionality in one place
Handles token tracking, free tier limits, and structured data output
"""

import json
import httpx
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from google import genai
from google.genai import types as genai_types
from PIL import Image
from io import BytesIO
from dataclasses import dataclass, asdict
import hashlib
import os
import re


@dataclass
class AnalysisResult:
    """Structured result with different views"""
    # Consumer view (minimal for UI)
    consumer_data: Dict[str, Any]
    
    # Brand view (detailed for analytics)
    brand_data: Dict[str, Any]
    
    # Raw data (for storage/reprocessing)
    raw_data: Dict[str, Any]
    
    # Metadata
    tokens_used: int
    cost_estimate: float
    processing_time: float


class ProductAnalyzer:
    """Complete product analyzer with token optimization and structured output"""
    
    # Free tier limits
    FREE_TIER_LIMITS = {
        'requests_per_day': 1500,
        'tokens_per_day': 1000000,  # 1M tokens
        'requests_per_minute': 15
    }
    
    # Pricing (for tracking even on free tier)
    PRICING = {
        'gemini-2.5-flash': {
            'input': 0.00001875,   # per 1K tokens
            'output': 0.0000375,    # per 1K tokens
            'image': 0.0001315      # per image
        }
    }
    
    def __init__(self, api_key: str, usage_file: str = 'usage_tracking.json'):
        # Initialize new genai client
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.0-flash-exp"
        self.usage_file = usage_file
        self.usage = self._load_usage()
        
        # Optimized prompts for different modes
        self.prompts = {
            'minimal': """JSON only:
{"n":"name","b":"brand","i":["top5 ingredients"],"nu":{"e":kcal,"p":protein,"c":carbs,"s":sugar,"f":fat,"so":sodium},"sq":{"s":safety_0-5,"q":quality_0-5,"u":usability_0-5,"o":origin_0-5,"r":responsibility_0-5},"w":["warnings max3"],"rec":"1line recommendation"}""",
            
            'standard': """You are a food product analysis assistant. Analyze the provided product using the images and the context below. Return a single, strictly valid JSON object only (no comments or markdown).

Scoring definition (0–5 integers):
- S (Safety): 0 very unsafe … 5 very safe.
  Consider: allergens disclosure, contaminant risk, shelf life clarity, correct storage, warnings, regulatory symbols (e.g., FSSAI/marking), absence of misleading "medical" claims.
- Q (Quality): 0 poor … 5 excellent.
  Consider: ingredient quality (whole vs ultra-processed), oil quality (e.g., palm vs peanut/olive), added sugar/sodium load, additive count (emulsifiers, colors, preservatives), overall macronutrient balance.
- U (Usability): 0 unusable … 5 excellent.
  Consider: clarity of pack info (name, weight, nutrition table), preparation simplicity, resealability, serving guidance, label readability (contrast, font).
- O (Origin): 0 unknown/opaque … 5 transparent/sustainable.
  Consider: country of origin, sourcing transparency, supply-chain claims, certifications (e.g., organic), local sourcing, batch/lot traceability.
- R (Responsibility): 0 irresponsible … 5 exemplary.
  Consider: recyclability symbols, reduced-plastic claims, responsible marketing (no kid-targeted ultra-processed claims), certifications (Fairtrade/eco), corporate responsibility notes.

Output JSON schema:
{
  "product": {"name": "", "brand": "", "category": ""},
  "ingredients": ["..."],
  "nutrition": {
    "energy_kcal": 0,
    "protein_g": 0,
    "carbs_g": 0,
    "sugar_g": 0,
    "fat_g": 0,
    "saturated_fat_g": 0,
    "sodium_mg": 0
  },
  "claims": ["..."],
  "warnings": ["..."],
  "squor": {
    "s": 0, "q": 0, "u": 0, "o": 0, "r": 0,
    "reasons": {
      "s": "1–2 sentences citing evidence from label/ingredients/nutrition.",
      "q": "…",
      "u": "…",
      "o": "…",
      "r": "…"
    }
  },
  "verdict": {
    "overall_0_5": 0,
    "recommendation": "1–2 sentence actionable recommendation"
  },
  "best_image": {
    "index": 1,
    "reason": "Why this image is best for product display (clear front pack, brand/name visible, focus/lighting)"
  },
  "confidence": 0.8
}

Rules:
- Use only the provided images and context. Do not fabricate.
- If a field is not visible/derivable, keep a reasonable default (e.g., 0 or empty) and explain in reasons.
- Return strictly valid JSON only.""",
            
            'detailed': """You are a comprehensive food product analysis assistant. Provide detailed analysis with complete SQUOR breakdown and justifications. Return strictly valid JSON only.

[Same scoring definitions as standard mode]

Output comprehensive analysis with detailed reasoning for each SQUOR dimension, complete nutritional analysis with daily value percentages where possible, verified claims vs actual content analysis, and specific actionable recommendations."""
        }
    
    def _load_usage(self) -> Dict[str, Any]:
        """Load or initialize usage tracking"""
        if os.path.exists(self.usage_file):
            with open(self.usage_file, 'r') as f:
                data = json.load(f)
                if data.get('date') != str(date.today()):
                    return self._reset_usage()
                return data
        return self._reset_usage()
    
    def _reset_usage(self) -> Dict[str, Any]:
        """Reset daily usage"""
        return {
            'date': str(date.today()),
            'requests': 0,
            'tokens': 0,
            'products': 0,
            'cost': 0.0,
            'started_at': datetime.now().isoformat()
        }
    
    def _save_usage(self):
        """Save usage data"""
        with open(self.usage_file, 'w') as f:
            json.dump(self.usage, f, indent=2)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def _track_usage(self, prompt: str, images: int, response: str) -> Dict[str, Any]:
        """Track token usage and costs"""
        input_tokens = self._estimate_tokens(prompt) + (images * 85)  # ~85 tokens per image
        output_tokens = self._estimate_tokens(response)
        total_tokens = input_tokens + output_tokens
        
        # Calculate cost
        cost = (
            (input_tokens / 1000) * self.PRICING['gemini-2.5-flash']['input'] +
            (output_tokens / 1000) * self.PRICING['gemini-2.5-flash']['output'] +
            (images * self.PRICING['gemini-2.5-flash']['image'])
        )
        
        # Update usage
        self.usage['requests'] += 1
        self.usage['tokens'] += total_tokens
        self.usage['cost'] += cost
        self.usage['products'] += 1
        self._save_usage()
        
        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens,
            'cost': cost
        }
    
    def check_limits(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if within free tier limits"""
        remaining_requests = self.FREE_TIER_LIMITS['requests_per_day'] - self.usage['requests']
        remaining_tokens = self.FREE_TIER_LIMITS['tokens_per_day'] - self.usage['tokens']
        
        if remaining_requests <= 0:
            return False, "Daily request limit reached", {'remaining_requests': 0, 'remaining_tokens': remaining_tokens}
        
        if remaining_tokens <= 0:
            return False, "Daily token limit reached", {'remaining_requests': remaining_requests, 'remaining_tokens': 0}
        
        # Calculate what's possible
        avg_tokens_per_product = self.usage['tokens'] / max(self.usage['products'], 1)
        possible_products = min(
            remaining_requests,
            remaining_tokens // max(avg_tokens_per_product, 400)
        )
        
        return True, f"Can process ~{int(possible_products)} more products today", {
            'remaining_requests': remaining_requests,
            'remaining_tokens': remaining_tokens,
            'possible_products': int(possible_products)
        }
    
    async def analyze_product_from_urls(
        self,
        image_urls: List[str],
        product_url: str = "",
        product_info: dict = None,
        mode: str = 'standard'
    ) -> AnalysisResult:
        """Analyze product using image URLs with URL context enabled"""
        
        start_time = datetime.now()
        
        # Check limits
        can_proceed, message, limits_info = self.check_limits()
        if not can_proceed:
            raise Exception(f"Free tier limit reached: {message}")
        
        # Build prompt with URLs
        prompt = self.prompts[mode]
        
        # Add product context if available
        if product_info:
            prompt += f"\n\nProduct context:\n"
            prompt += f"Name: {product_info.get('name', 'Unknown')}\n"
            prompt += f"Brand: {product_info.get('brand', 'Unknown')}\n"
            prompt += f"Price: {product_info.get('price', 'Unknown')}\n"
            prompt += f"Category: {product_info.get('category', 'Unknown')}\n"
        
        # Add image URLs
        prompt += "\n\nAnalyze these product images:\n"
        for i, url in enumerate(image_urls[:5], 1):  # Limit to 5 images
            prompt += f"Image {i}: {url}\n"
        
# Log prompt and images for debugging (only in development)
        if os.getenv("DEBUG_AI_PROMPTS", "false").lower() == "true":
            print("🔍 PROMPT BEING SENT TO GEMINI:")
            print(prompt[:200] + "..." if len(prompt) > 200 else prompt)
            print(f"📸 IMAGE URLs: {len(image_urls)} images")
        
        # Configure tools with URL context
        tools = [
            {"url_context": {}}  # Enable URL context tool
        ]
        
        # Configure generation (no token limit for complete responses)
        config = genai_types.GenerateContentConfig(
            tools=tools,
            temperature=0.1,
            candidate_count=1
        )
        
        try:
            # Generate content using new client with URL context
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=config
            )
            
            # Extract response text from new client format
            response_text = ""
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    # Combine all text parts
                    text_parts = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    response_text = "".join(text_parts)
            
            # Log AI response for debugging (only in development)
            if os.getenv("DEBUG_AI_RESPONSES", "false").lower() == "true":
                print(f"🤖 GEMINI RESPONSE ({len(response_text)} chars):")
                print(response_text[:500] + "..." if len(response_text) > 500 else response_text)
            
            if not response_text:
                # Check if this might be quota exhaustion
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    if response.usage_metadata.total_token_count == 0:
                        raw_data = {"error": "Quota exhausted - Gemini returned 0 tokens", "quota_exhausted": True}
                        print("🚨 QUOTA EXHAUSTED: Gemini returned 0 tokens - daily limit may be reached")
                    else:
                        raw_data = {"error": "No response text from Gemini", "response_debug": str(response)[:500]}
                else:
                    raw_data = {"error": "No response text from Gemini", "response_debug": str(response)[:500]}
            else:
                # Extract JSON from response (handle markdown code blocks)
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if not json_match:
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(1) if json_match.lastindex else json_match.group()
                    raw_data = json.loads(json_str)
                    if os.getenv("DEBUG_AI_RESPONSES", "false").lower() == "true":
                        print("✅ Successfully parsed JSON from AI response")
                else:
                    raw_data = {"error": "Failed to parse JSON", "raw": response_text}
                    if os.getenv("DEBUG_AI_RESPONSES", "false").lower() == "true":
                        print("❌ Failed to parse JSON from AI response")
            
            # Track usage from response metadata
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage_info = {
                    'input_tokens': response.usage_metadata.prompt_token_count or 0,
                    'output_tokens': response.usage_metadata.candidates_token_count or 0,
                    'total_tokens': response.usage_metadata.total_token_count or 0,
                    'image_tokens': 0  # Will be calculated from tool_use tokens
                }
                
                # Extract image tokens from tool use
                if hasattr(response.usage_metadata, 'tool_use_prompt_tokens_details'):
                    for detail in response.usage_metadata.tool_use_prompt_tokens_details:
                        if hasattr(detail, 'modality') and str(detail.modality) == 'MediaModality.IMAGE':
                            usage_info['image_tokens'] = detail.token_count
                
                # Calculate cost
                cost = (
                    (usage_info['input_tokens'] / 1000) * self.PRICING['gemini-2.5-flash']['input'] +
                    (usage_info['output_tokens'] / 1000) * self.PRICING['gemini-2.5-flash']['output'] +
                    (usage_info['image_tokens'] / 1000) * self.PRICING['gemini-2.5-flash']['image']
                )
                usage_info['cost'] = cost
                
                # Update usage tracking
                self.usage['requests'] += 1
                self.usage['tokens'] += usage_info['total_tokens']
                self.usage['cost'] += cost
                self.usage['products'] += 1
                self._save_usage()
            else:
                # Fallback to old tracking method
                usage_info = self._track_usage(prompt, len(image_urls), response_text)
            
            # Process into different views
            consumer_data = self._create_consumer_view(raw_data, mode)
            brand_data = self._create_brand_view(raw_data, mode)
            
            # Add metadata
            raw_data['_metadata'] = {
                'analyzed_at': datetime.now().isoformat(),
                'mode': mode,
                'model': 'gemini-2.5-flash',
                'images_analyzed': len(image_urls),
                'product_url': product_url,
                **usage_info
            }
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return AnalysisResult(
                consumer_data=consumer_data,
                brand_data=brand_data,
                raw_data=raw_data,
                tokens_used=usage_info['total_tokens'],
                cost_estimate=usage_info['cost'],
                processing_time=processing_time
            )
            
        except Exception as e:
            # Return error result
            error_data = {'error': str(e), 'timestamp': datetime.now().isoformat()}
            return AnalysisResult(
                consumer_data=error_data,
                brand_data=error_data,
                raw_data=error_data,
                tokens_used=0,
                cost_estimate=0,
                processing_time=(datetime.now() - start_time).total_seconds()
            )

    def analyze_product(
        self, 
        images: List[Image], 
        product_url: str = "",
        mode: str = 'standard'  # 'minimal', 'standard', 'detailed'
    ) -> AnalysisResult:
        """Main analysis function with different modes"""
        
        start_time = datetime.now()
        
        # Check limits
        can_proceed, message, limits_info = self.check_limits()
        if not can_proceed:
            raise Exception(f"Free tier limit reached: {message}")
        
        # Select prompt and images based on mode
        prompt = self.prompts[mode]
        
        if mode == 'minimal':
            selected_images = images[:2]  # Only front and back
            max_tokens = 200
        elif mode == 'standard':
            selected_images = images[:3]  # Front, back, nutrition
            max_tokens = 500
        else:  # detailed
            selected_images = images[:5]  # All important angles
            max_tokens = 1000
        
        # Configure generation
        generation_config = genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.1,
            candidate_count=1
        )
        
        try:
            # Generate content
            response = self.model.generate_content(
                [prompt] + selected_images,
                generation_config=generation_config
            )
            
            # Extract JSON from response
            response_text = response.text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                raw_data = json.loads(json_match.group())
            else:
                raw_data = {"error": "Failed to parse JSON", "raw": response_text}
            
            # Track usage
            usage_info = self._track_usage(prompt, len(selected_images), response_text)
            
            # Process into different views
            consumer_data = self._create_consumer_view(raw_data, mode)
            brand_data = self._create_brand_view(raw_data, mode)
            
            # Add metadata to raw data
            raw_data['_metadata'] = {
                'analyzed_at': datetime.now().isoformat(),
                'mode': mode,
                'model': 'gemini-2.5-flash',
                'images_analyzed': len(selected_images),
                'product_url': product_url,
                **usage_info
            }
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return AnalysisResult(
                consumer_data=consumer_data,
                brand_data=brand_data,
                raw_data=raw_data,
                tokens_used=usage_info['total_tokens'],
                cost_estimate=usage_info['cost'],
                processing_time=processing_time
            )
            
        except Exception as e:
            # Return error result
            error_data = {'error': str(e), 'timestamp': datetime.now().isoformat()}
            return AnalysisResult(
                consumer_data=error_data,
                brand_data=error_data,
                raw_data=error_data,
                tokens_used=0,
                cost_estimate=0,
                processing_time=(datetime.now() - start_time).total_seconds()
            )
    
    def _create_consumer_view(self, data: Dict, mode: str) -> Dict[str, Any]:
        """Create minimal consumer-friendly view"""
        if mode == 'minimal':
            # Expand abbreviated keys
            name = data.get('n', 'Unknown')
            brand = data.get('b', 'Unknown')
            squor_scores = data.get('sq', {})
            # Calculate weighted SQUOR score
            overall_squor = (
                squor_scores.get('s', 0) * 0.25 +  # Safety 25%
                squor_scores.get('q', 0) * 0.25 +  # Quality 25%
                squor_scores.get('u', 0) * 0.15 +  # Usability 15%
                squor_scores.get('o', 0) * 0.15 +  # Origin 15%
                squor_scores.get('r', 0) * 0.20    # Responsibility 20%
            )
            warnings = data.get('w', [])
            recommendation = data.get('rec', '')
        else:
            # Standard/detailed format
            product_info = data.get('product', {})
            name = product_info.get('name', 'Unknown')
            brand = product_info.get('brand', 'Unknown')
            scores = data.get('scores', {})
            # Calculate weighted SQUOR score
            overall_squor = (
                scores.get('safety', 0) * 0.25 +
                scores.get('quality', 0) * 0.25 +
                scores.get('usability', 0) * 0.15 +
                scores.get('origin', 0) * 0.15 +
                scores.get('responsibility', 0) * 0.20
            )
            warnings = data.get('warnings', [])
            verdict = data.get('verdict', {})
            recommendation = verdict.get('recommendation', '')
        
        # Generate ID
        product_id = hashlib.md5(f"{brand}:{name}".encode()).hexdigest()[:12]
        
        # Determine SQUOR rating
        if overall_squor >= 80:
            squor_rating = "🟢"
            squor_label = "Excellent"
        elif overall_squor >= 60:
            squor_rating = "🟡"
            squor_label = "Good"
        elif overall_squor >= 40:
            squor_rating = "🟠"
            squor_label = "Fair"
        else:
            squor_rating = "🔴"
            squor_label = "Poor"
        
        return {
            'product_id': product_id,
            'name': name,
            'brand': brand,
            'squor_score': round(overall_squor, 1),
            'squor_rating': squor_rating,
            'squor_label': squor_label,
            'squor_components': scores if mode != 'minimal' else squor_scores,
            'key_warnings': warnings[:3],  # Top 3 warnings only
            'recommendation': recommendation
        }
    
    def _create_brand_view(self, data: Dict, mode: str) -> Dict[str, Any]:
        """Create detailed brand analytics view"""
        if mode == 'minimal':
            # Limited data available
            return {
                'limited_analysis': True,
                'ingredients_count': len(data.get('i', [])),
                'basic_nutrition': data.get('nu', {}),
                'health_score': data.get('h', 0)
            }
        
        # Full analysis for standard/detailed modes
        return {
            'product_details': data.get('product', {}),
            'ingredients_analysis': {
                'full_list': data.get('ingredients', []),
                'count': len(data.get('ingredients', [])),
                'concerns': [i for i in data.get('ingredients', []) if any(
                    concern in i.lower() for concern in ['palm oil', 'sugar', 'sodium', 'artificial']
                )]
            },
            'nutrition_profile': data.get('nutrition', {}),
            'score_breakdown': data.get('scores', {}),
            'claims_verification': data.get('claims', []),
            'compliance_status': {
                'has_allergen_info': bool(data.get('warnings')),
                'has_nutrition_label': bool(data.get('nutrition')),
                'claims_substantiated': len(data.get('claims', [])) > 0
            },
            'improvement_opportunities': self._generate_improvements(data),
            'competitive_position': 'Above average' if sum(data.get('scores', {}).values()) > 60 else 'Below average'
        }
    
    def _generate_improvements(self, data: Dict) -> List[str]:
        """Generate improvement suggestions"""
        improvements = []
        
        nutrition = data.get('nutrition', {})
        if nutrition.get('sodium', 0) > 400:
            improvements.append("Reduce sodium content by 25%")
        if nutrition.get('sugar', 0) > 15:
            improvements.append("Lower sugar content")
        if nutrition.get('saturated_fat', 0) > 5:
            improvements.append("Replace with healthier fats")
        
        ingredients = data.get('ingredients', [])
        if any('palm oil' in i.lower() for i in ingredients):
            improvements.append("Consider sustainable oil alternatives")
        
        return improvements[:3]  # Top 3 suggestions
    
    def get_usage_report(self) -> str:
        """Get comprehensive usage report"""
        can_proceed, message, limits_info = self.check_limits()
        
        # Calculate rates
        hours_elapsed = (datetime.now() - datetime.fromisoformat(self.usage['started_at'])).total_seconds() / 3600
        rate_per_hour = self.usage['products'] / max(hours_elapsed, 1)
        
        # Average metrics
        avg_tokens = self.usage['tokens'] / max(self.usage['products'], 1)
        avg_cost = self.usage['cost'] / max(self.usage['products'], 1)
        
        report = f"""
📊 USAGE REPORT - {date.today()}
{'='*60}

FREE TIER STATUS:
✓ Requests: {self.usage['requests']:,} / {self.FREE_TIER_LIMITS['requests_per_day']:,} ({limits_info['remaining_requests']:,} left)
✓ Tokens:   {self.usage['tokens']:,} / {self.FREE_TIER_LIMITS['tokens_per_day']:,} ({limits_info['remaining_tokens']:,} left)
✓ Products: {self.usage['products']:,} analyzed

EFFICIENCY:
• Tokens/product: {avg_tokens:.0f}
• Cost/product:   ${avg_cost:.6f}
• Processing rate: {rate_per_hour:.1f} products/hour
• Can analyze:    ~{limits_info.get('possible_products', 0)} more today

STATUS: {'✅ ' + message if can_proceed else '❌ ' + message}

COST TRACKING (even on free tier):
• Total cost value: ${self.usage['cost']:.4f}
• Hourly rate:      ${self.usage['cost']/max(hours_elapsed, 1):.4f}
• Daily projection: ${self.usage['cost']/max(hours_elapsed, 1)*24:.2f}
{'='*60}
"""
        return report
    
    def batch_analyze(self, products: List[Dict], mode: str = 'standard') -> List[AnalysisResult]:
        """Analyze multiple products efficiently"""
        results = []
        
        for i, product in enumerate(products):
            # Check limits before each product
            can_proceed, message, _ = self.check_limits()
            if not can_proceed:
                print(f"⚠️  Stopping at product {i+1}: {message}")
                break
            
            try:
                result = self.analyze_product(
                    images=product['images'],
                    product_url=product.get('url', ''),
                    mode=mode
                )
                results.append(result)
                
                print(f"✅ {i+1}. {result.consumer_data['name']} - Score: {result.consumer_data['health_score']}")
                
            except Exception as e:
                print(f"❌ {i+1}. Error: {e}")
        
        # Print summary
        print(f"\n📊 Batch complete: {len(results)} products analyzed")
        print(self.get_usage_report())
        
        return results


# Example usage
if __name__ == "__main__":
    print("🚀 UNIFIED PRODUCT ANALYZER")
    print("All functionality in one clean module!")
    print("\nFeatures:")
    print("✓ Token tracking & optimization")
    print("✓ Free tier management")
    print("✓ Multiple analysis modes (minimal/standard/detailed)")
    print("✓ Structured data output (consumer/brand/raw)")
    print("✓ Batch processing")
    print("✓ Usage reporting")
    
    # Example API
    print("\nAPI Usage:")
    print("""
# Initialize
analyzer = ProductAnalyzer(api_key)

# Analyze single product
result = analyzer.analyze_product(images, mode='standard')
print(result.consumer_data)  # For UI
print(result.brand_data)     # For analytics
print(result.raw_data)       # For storage

# Check usage
print(analyzer.get_usage_report())

# Batch process
results = analyzer.batch_analyze(products, mode='minimal')
""")
