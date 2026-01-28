"""
Manufacturing Copilot - Claude-Powered Manufacturing Intelligence

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

The main AI interface for manufacturing operations:
- Natural language Q&A about production
- Anomaly explanation
- Decision recommendations
- Process optimization suggestions
- Knowledge base search (RAG)

Powered by Claude for intelligent analysis and plain-language responses.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

from .context_builder import ContextBuilder, ProductionContext
from .anomaly_explainer import AnomalyExplainer, AnomalyData, AnomalyExplanation, AnomalyType
from .decision_recommender import DecisionRecommender, Decision, DecisionType

logger = logging.getLogger(__name__)


class CopilotMode(str, Enum):
    """Operating modes for the copilot."""
    ASSISTANT = "assistant"      # Answer questions, explain
    ADVISOR = "advisor"          # Make recommendations
    AUTONOMOUS = "autonomous"    # Take actions automatically
    ANALYST = "analyst"          # Deep analysis mode


@dataclass
class CopilotConfig:
    """Configuration for the Manufacturing Copilot."""
    api_key: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.3
    mode: CopilotMode = CopilotMode.ASSISTANT
    auto_approve_threshold: float = 0.95
    include_lego_knowledge: bool = True
    include_manufacturing_standards: bool = True


@dataclass
class CopilotResponse:
    """Response from the Manufacturing Copilot."""
    response_id: str
    timestamp: datetime
    query: str
    response_text: str
    mode: CopilotMode

    # Structured data (if applicable)
    decisions: List[Decision] = field(default_factory=list)
    anomaly_explanations: List[AnomalyExplanation] = field(default_factory=list)

    # Metadata
    context_used: Optional[ProductionContext] = None
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'response_id': self.response_id,
            'timestamp': self.timestamp.isoformat(),
            'query': self.query,
            'response_text': self.response_text,
            'mode': self.mode.value,
            'decisions': [d.to_dict() for d in self.decisions],
            'confidence': self.confidence,
            'processing_time_ms': self.processing_time_ms,
        }


class ManufacturingCopilot:
    """
    Claude-powered Manufacturing Copilot.

    Provides intelligent assistance for manufacturing operations including:
    - Natural language Q&A
    - Anomaly explanation
    - Decision support
    - Process optimization
    - Knowledge search
    """

    # LEGO manufacturing knowledge base
    LEGO_KNOWLEDGE = """
## LEGO Brick Manufacturing Standards

### Critical Dimensions
- Stud pitch: 8.0mm ±0.02mm
- Stud diameter: 4.8mm ±0.02mm
- Stud height: 1.8mm ±0.1mm
- Wall thickness: 1.6mm ±0.05mm
- Plate height: 3.2mm ±0.02mm
- Brick height (3 plates): 9.6mm ±0.05mm
- Inter-brick clearance: 0.1mm per side
- Pin hole diameter: 4.9mm ±0.02mm
- Technic hole diameter: 4.85mm ±0.02mm
- Anti-stud ID: 6.51mm ±0.02mm

### Clutch Power Requirements
- Optimal range: 1.0-3.0 Newtons
- Below 1.0N: Too loose, bricks fall apart
- Above 3.0N: Too tight, difficult to separate

### Quality Metrics
- Target Cpk: ≥1.33 for non-critical dimensions
- Target Cpk: ≥1.67 for critical dimensions (studs)
- DPMO target: <10 (approaching Six Sigma)
- First Pass Yield target: 99.5%

### Common Defects in 3D Printed LEGO
1. Under-extrusion → Loose clutch power
2. Over-extrusion → Tight clutch power
3. Layer adhesion issues → Weak structure
4. Warping → Poor fit
5. Stringing → Surface quality issues
6. Z-wobble → Dimensional variation

### Print Settings for PLA (LEGO compatible)
- Layer height: 0.12mm
- First layer: 0.2mm
- Nozzle temp: 210°C
- Bed temp: 60°C
- Infill: 100% (for clutch power)
- Perimeters: 4 minimum
- Print speed: 40mm/s
"""

    MANUFACTURING_STANDARDS = """
## Manufacturing Standards Reference

### OEE (Overall Equipment Effectiveness)
OEE = Availability × Performance × Quality
- Availability = Run Time / Planned Production Time
- Performance = (Ideal Cycle Time × Total Count) / Run Time
- Quality = Good Count / Total Count
- World-class target: 85%+

### SPC (Statistical Process Control)
Control Chart Rules (Western Electric):
- Rule 1: One point beyond 3σ (out of control)
- Rule 2: 9 consecutive points on one side of centerline
- Rule 3: 6 consecutive points steadily increasing/decreasing
- Rule 4: 14 consecutive points alternating up/down
- Zone A: 2 of 3 beyond 2σ
- Zone B: 4 of 5 beyond 1σ
- Zone C: 8 consecutive on one side

### Process Capability
- Cp = (USL - LSL) / (6σ)
- Cpk = min((USL - μ)/(3σ), (μ - LSL)/(3σ))
- Cpk ≥ 1.33: Capable process
- Cpk ≥ 1.67: Excellent process
- Cpk ≥ 2.00: Six Sigma process

### ISA-95 Levels
- Level 0: Physical processes (sensors, actuators)
- Level 1: Basic controls (PLCs, controllers)
- Level 2: Supervisory control (SCADA, HMI)
- Level 3: MES/MOM (scheduling, quality, maintenance)
- Level 4: ERP (business planning)
"""

    def __init__(
        self,
        config: Optional[CopilotConfig] = None,
        context_builder: Optional[ContextBuilder] = None,
        anomaly_explainer: Optional[AnomalyExplainer] = None,
        decision_recommender: Optional[DecisionRecommender] = None,
    ):
        self.config = config or CopilotConfig()
        self.context_builder = context_builder or ContextBuilder()
        self.anomaly_explainer = anomaly_explainer or AnomalyExplainer()
        self.decision_recommender = decision_recommender or DecisionRecommender()

        # Initialize Claude client
        if ANTHROPIC_AVAILABLE:
            api_key = self.config.api_key or os.getenv('ANTHROPIC_API_KEY')
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
            else:
                self.client = None
                logger.warning("No Anthropic API key found")
        else:
            self.client = None
            logger.warning("Anthropic library not available")

        # Conversation history for context
        self.conversation_history: List[Dict[str, str]] = []

    def _build_system_prompt(self) -> str:
        """Build the system prompt with knowledge base."""
        prompt = """You are an expert Manufacturing Copilot for the LegoMCP Industry 4.0 Digital Manufacturing Platform.
You help operators, engineers, and managers understand and optimize LEGO-compatible brick manufacturing.

Your responsibilities:
1. Answer questions about production status, quality, and equipment
2. Explain anomalies and defects in plain language
3. Recommend actions for scheduling, quality, and maintenance
4. Provide process optimization suggestions
5. Help troubleshoot manufacturing issues

Always:
- Be concise and actionable
- Reference specific metrics and data when available
- Explain technical concepts in accessible terms
- Prioritize safety and quality
- Consider cost and efficiency implications

"""
        if self.config.include_lego_knowledge:
            prompt += self.LEGO_KNOWLEDGE + "\n\n"

        if self.config.include_manufacturing_standards:
            prompt += self.MANUFACTURING_STANDARDS + "\n\n"

        return prompt

    async def ask(
        self,
        question: str,
        include_context: bool = True,
        context_types: Optional[List[str]] = None,
    ) -> CopilotResponse:
        """
        Ask the copilot a question.

        Args:
            question: Natural language question
            include_context: Whether to include production context
            context_types: Specific context types to include

        Returns:
            CopilotResponse with answer
        """
        from uuid import uuid4
        import time

        start_time = time.time()

        # Build context
        context = None
        context_text = ""
        if include_context:
            context = await self.context_builder.build_for_question(question)
            context_text = context.to_prompt_text()

        # Build messages
        messages = []

        if context_text:
            messages.append({
                "role": "user",
                "content": f"Current Production Context:\n\n{context_text}\n\n---\n\nQuestion: {question}"
            })
        else:
            messages.append({
                "role": "user",
                "content": question
            })

        # Get response from Claude
        response_text = await self._call_claude(messages)

        processing_time = (time.time() - start_time) * 1000

        return CopilotResponse(
            response_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            query=question,
            response_text=response_text,
            mode=self.config.mode,
            context_used=context,
            confidence=0.85,
            processing_time_ms=processing_time,
        )

    async def explain_anomaly(
        self,
        anomaly: AnomalyData,
        verbose: bool = False,
    ) -> CopilotResponse:
        """
        Explain a production anomaly.

        Args:
            anomaly: Anomaly data to explain
            verbose: Whether to include detailed technical info

        Returns:
            CopilotResponse with explanation
        """
        from uuid import uuid4
        import time

        start_time = time.time()

        # Get structured explanation
        explanation = await self.anomaly_explainer.explain_anomaly(anomaly, verbose=verbose)

        # Optionally enhance with Claude
        if self.client:
            prompt = f"""
Please provide a concise explanation of this manufacturing anomaly for an operator:

Type: {anomaly.anomaly_type.value}
Source: {anomaly.source}
Metric: {anomaly.metric_name}
Value: {anomaly.metric_value}
Context: {anomaly.context}

Initial Analysis:
{explanation.summary}

Root Causes:
{chr(10).join(f'- {rc.description} ({rc.probability*100:.0f}% likely)' for rc in explanation.root_causes)}

Please:
1. Explain what happened in plain language
2. Describe the potential impact
3. Recommend immediate actions
4. Suggest preventive measures
"""
            messages = [{"role": "user", "content": prompt}]
            response_text = await self._call_claude(messages)
        else:
            response_text = explanation.detailed_explanation

        processing_time = (time.time() - start_time) * 1000

        return CopilotResponse(
            response_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            query=f"Explain anomaly: {anomaly.anomaly_type.value}",
            response_text=response_text,
            mode=CopilotMode.ANALYST,
            anomaly_explanations=[explanation],
            confidence=explanation.confidence_score,
            processing_time_ms=processing_time,
        )

    async def recommend_action(
        self,
        situation: str,
        decision_type: DecisionType = DecisionType.SCHEDULE,
        data: Optional[Dict[str, Any]] = None,
    ) -> CopilotResponse:
        """
        Get action recommendation for a situation.

        Args:
            situation: Description of the situation
            decision_type: Type of decision needed
            data: Relevant data for the decision

        Returns:
            CopilotResponse with recommendation
        """
        from uuid import uuid4
        import time

        start_time = time.time()

        data = data or {}
        decision = None

        # Get structured decision
        if decision_type == DecisionType.SCHEDULE:
            decision = await self.decision_recommender.recommend_schedule_action(
                current_schedule=data.get('schedule', {}),
                disruption=data.get('disruption'),
            )
        elif decision_type == DecisionType.QUALITY:
            decision = await self.decision_recommender.recommend_quality_action(
                anomaly=data.get('anomaly', {}),
            )
        elif decision_type == DecisionType.MAINTENANCE:
            decision = await self.decision_recommender.recommend_maintenance_action(
                equipment_state=data.get('equipment', {}),
            )
        elif decision_type == DecisionType.ROUTING:
            decision = await self.decision_recommender.recommend_routing(
                operation=data.get('operation', {}),
                available_machines=data.get('machines', []),
            )

        if decision:
            response_text = f"""
**Recommendation:** {decision.recommendation}

**Rationale:**
{decision.rationale}

**Confidence:** {decision.confidence.value} ({decision.confidence_score*100:.0f}%)

**Alternatives:**
{chr(10).join(f'- {alt.description}' for alt in decision.alternatives)}

**Requires Approval:** {'Yes' if decision.requires_approval else 'No'}
"""
        else:
            response_text = f"Unable to generate recommendation for {decision_type.value} decision."

        processing_time = (time.time() - start_time) * 1000

        return CopilotResponse(
            response_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            query=situation,
            response_text=response_text,
            mode=CopilotMode.ADVISOR,
            decisions=[decision] if decision else [],
            confidence=decision.confidence_score if decision else 0.0,
            processing_time_ms=processing_time,
        )

    async def optimize_process(
        self,
        process_data: Dict[str, Any],
        optimization_goals: List[str],
    ) -> CopilotResponse:
        """
        Suggest process optimizations.

        Args:
            process_data: Historical process data
            optimization_goals: What to optimize (quality, speed, cost, etc.)

        Returns:
            CopilotResponse with optimization suggestions
        """
        from uuid import uuid4
        import time

        start_time = time.time()

        goals_text = ", ".join(optimization_goals)

        prompt = f"""
Analyze this manufacturing process data and suggest optimizations for: {goals_text}

Process Data:
- Machine: {process_data.get('machine', 'Unknown')}
- Part: {process_data.get('part', 'Unknown')}
- Current OEE: {process_data.get('oee', 'N/A')}%
- First Pass Yield: {process_data.get('fpy', 'N/A')}%
- Cycle Time: {process_data.get('cycle_time', 'N/A')} minutes
- Top Defects: {', '.join(process_data.get('top_defects', []))}
- Recent Changes: {', '.join(process_data.get('recent_changes', []))}

Please provide:
1. Top 3 optimization opportunities
2. Expected improvement for each
3. Implementation steps
4. Potential risks
5. Priority ranking
"""

        messages = [{"role": "user", "content": prompt}]
        response_text = await self._call_claude(messages)

        processing_time = (time.time() - start_time) * 1000

        return CopilotResponse(
            response_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            query=f"Optimize for: {goals_text}",
            response_text=response_text,
            mode=CopilotMode.ANALYST,
            confidence=0.75,
            processing_time_ms=processing_time,
        )

    async def diagnose_defect(
        self,
        defect_info: Dict[str, Any],
        production_context: Optional[ProductionContext] = None,
    ) -> CopilotResponse:
        """
        Diagnose a quality defect.

        Args:
            defect_info: Information about the defect
            production_context: Current production context

        Returns:
            CopilotResponse with diagnosis
        """
        from uuid import uuid4
        import time

        start_time = time.time()

        defect_type = defect_info.get('type', 'unknown')
        part = defect_info.get('part', 'unknown')
        machine = defect_info.get('machine', 'unknown')

        context_text = ""
        if production_context:
            context_text = production_context.to_prompt_text()

        prompt = f"""
Diagnose this manufacturing defect and recommend corrective actions:

**Defect Information:**
- Type: {defect_type}
- Part: {part}
- Machine: {machine}
- Description: {defect_info.get('description', 'N/A')}
- Quantity Affected: {defect_info.get('quantity', 'N/A')}
- Discovery Method: {defect_info.get('discovery_method', 'inspection')}

{f"**Production Context:**{chr(10)}{context_text}" if context_text else ""}

**Recent Process History:**
- Previous 10 parts: {defect_info.get('recent_quality', 'Unknown')}
- Last process change: {defect_info.get('last_change', 'Unknown')}
- Material batch: {defect_info.get('material_batch', 'Unknown')}

Please provide:
1. Most likely root cause(s)
2. Immediate containment actions
3. Corrective actions
4. Verification steps
5. Preventive measures for the future

Focus on LEGO-specific quality requirements like clutch power and dimensional accuracy.
"""

        messages = [{"role": "user", "content": prompt}]
        response_text = await self._call_claude(messages)

        processing_time = (time.time() - start_time) * 1000

        return CopilotResponse(
            response_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            query=f"Diagnose defect: {defect_type} on {part}",
            response_text=response_text,
            mode=CopilotMode.ANALYST,
            context_used=production_context,
            confidence=0.80,
            processing_time_ms=processing_time,
        )

    async def _call_claude(self, messages: List[Dict[str, str]]) -> str:
        """Call Claude API."""
        if not self.client:
            return self._generate_fallback_response(messages)

        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=self._build_system_prompt(),
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return self._generate_fallback_response(messages)

    def _generate_fallback_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate fallback response when Claude is unavailable."""
        query = messages[-1].get('content', '') if messages else ''

        return f"""
**Note:** AI analysis is currently unavailable. Here's a basic response:

Your query: {query[:200]}...

For detailed analysis, please:
1. Check API key configuration
2. Verify network connectivity
3. Review the production dashboard for real-time data
4. Consult the BRICK_BUILDING_GUIDE.md for LEGO specifications

If this is urgent, please contact the system administrator.
"""

    async def start_conversation(self, initial_message: str) -> CopilotResponse:
        """Start a new conversation."""
        self.conversation_history = []
        return await self.ask(initial_message)

    async def continue_conversation(self, message: str) -> CopilotResponse:
        """Continue an existing conversation."""
        return await self.ask(message)

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []

    def get_capabilities(self) -> Dict[str, Any]:
        """Get copilot capabilities."""
        return {
            'mode': self.config.mode.value,
            'model': self.config.model,
            'available_functions': [
                'ask',
                'explain_anomaly',
                'recommend_action',
                'optimize_process',
                'diagnose_defect',
            ],
            'decision_types': [dt.value for dt in DecisionType],
            'anomaly_types': [at.value for at in AnomalyType],
            'claude_available': self.client is not None,
            'knowledge_bases': {
                'lego': self.config.include_lego_knowledge,
                'manufacturing': self.config.include_manufacturing_standards,
            },
        }
