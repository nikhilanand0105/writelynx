from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.providers import get_llm_provider
from backend.app.services.fact_validator import FactValidator
from backend.app.services.cost_governor import CostGovernor

class WritingAssistant:
    """
    Orchestrates context-aware academic editing across the four specified modes
    and validates every proposed modification against protected facts.
    """

    def __init__(self, provider_name: Optional[str] = None):
        self.provider_name = provider_name
        self.provider = get_llm_provider(provider_name)

    async def generate_document_suggestions(
        self,
        blocks: List[Dict[str, Any]],
        mode: str = "clarity",
        findings: Optional[List[Dict[str, Any]]] = None,
        document_id: Optional[str] = None,
        plan_tier: str = "basic",
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Batch generate editing suggestions across editable document blocks with cost gating.
        """
        suggestions: List[Dict[str, Any]] = []
        findings_by_block: Dict[str, List[Dict[str, Any]]] = {}
        if findings:
            for f in findings:
                b_id = f.get("block_id")
                if b_id:
                    findings_by_block.setdefault(b_id, []).append(f)

        for i, block in enumerate(blocks):
            # Check cost governor if DB session is present
            active_provider = self.provider
            if db and document_id:
                can_call, recommended = CostGovernor.can_make_ai_call(db, document_id, plan_tier)
                if not can_call:
                    active_provider = get_llm_provider("no_llm")
                elif recommended != self.provider_name and recommended in ("ollama", "no_llm"):
                    active_provider = get_llm_provider(recommended)

            # Skip protected structural blocks (e.g. titles, heading markers, references list)
            if block.get("is_protected") or block.get("block_type") in ["heading", "title", "reference_entry"]:
                continue

            orig_text = block.get("current_text", "").strip()
            if not orig_text or len(orig_text.split()) < 4:
                continue

            # Context window: surrounding paragraphs
            prev_text = blocks[i - 1]["current_text"] if i > 0 else ""
            next_text = blocks[i + 1]["current_text"] if i + 1 < len(blocks) else ""
            context = f"PREVIOUS: {prev_text}\nTARGET: {orig_text}\nNEXT: {next_text}"

            # Matched source text if overlapping
            matched_source_text = None
            block_findings = findings_by_block.get(block["id"], [])
            overlap_findings = [f for f in block_findings if "overlap" in f.get("finding_type", "")]
            if overlap_findings:
                matched_source_text = overlap_findings[0].get("source_matched_text")
                effective_mode = "source_grounded" if mode == "clarity" else mode
            else:
                effective_mode = mode

            # Call provider
            raw_sug = await active_provider.generate_suggestion(
                block_id=block["id"],
                original_text=orig_text,
                context=context,
                mode=effective_mode,
                matched_source_text=matched_source_text
            )

            # Record AI cost reservation
            prov_name = getattr(active_provider, "name", "no_llm")
            if db and document_id and prov_name not in ("no_llm", "ollama", "base"):
                prompt_toks = len(context.split()) * 2
                comp_toks = len(raw_sug.get("proposed_text", "").split()) * 2 if raw_sug else 0
                CostGovernor.record_cost(
                    db=db,
                    document_id=document_id,
                    plan_tier=plan_tier,
                    provider=prov_name,
                    model_name="default",
                    prompt_tokens=prompt_toks,
                    completion_tokens=comp_toks,
                )

            if raw_sug and raw_sug.get("proposed_text") != orig_text:
                proposed_text = raw_sug["proposed_text"]
                # Validate fact preservation
                facts_intact, violations = FactValidator.compare_facts(orig_text, proposed_text)
                
                sug_id = f"sug_{block['id']}_{len(suggestions)}"
                suggestions.append({
                    "id": sug_id,
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "issue_type": raw_sug.get("issue_type", mode),
                    "original_text": orig_text,
                    "proposed_text": proposed_text,
                    "reason": raw_sug.get("reason", "Editorial improvement"),
                    "citations_preserved": facts_intact,
                    "protected_entities_preserved": facts_intact,
                    "requires_user_review": True,
                    "confidence": raw_sug.get("confidence", 0.9),
                    "validation_status": "valid" if facts_intact else "warning",
                    "review_status": "pending"
                })

        return suggestions
