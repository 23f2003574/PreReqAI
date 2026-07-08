from backend.models import (
    Paper,
)

from backend.session import (
    LearningSession,
    RetrievedContext,
    TutorMode,
)

from .misconception_registry import (
    COMMON_MISCONCEPTIONS,
)

from .analogy_registry import (
    COMMON_ANALOGIES,
)

from .socratic_question_bank import (
    SOCRATIC_QUESTIONS,
)

from .quiz_generator import (
    QuizGenerator,
)


class TutorPromptBuilder:
    """
    Constructs prompts for every tutoring model.
    """

    def __init__(self):

        self.quiz_generator = (
            QuizGenerator()
        )

    def build(

        self,

        session: LearningSession,

        paper: Paper,

        context: RetrievedContext,

        question: str,

        mode: TutorMode,

    ) -> str:

        concepts = ", ".join(
            context.concepts
        )

        sections = ", ".join(
            context.sections
        )

        return f"""
You are PreReqAI.

Your objective is to help a learner understand
a research paper.

Paper:
{paper.metadata.title}

Current Topic:
{session.active_concept}

Relevant Concepts:
{concepts}

Relevant Sections:
{sections}

Learner Question:
{question}

Teaching Mode:
{mode.value}

Instructions:
{self._mode_instruction(mode)}

Common Misconceptions:
{self.misconception_examples(context)}

Relevant Analogies:
{self.analogy_examples(context)}

Possible Socratic Questions:
{self.socratic_questions(context)}

Suggested Quiz Questions:
{self.quiz_questions(context)}

Rules:

- Ground every answer in the supplied context.
- Avoid introducing unsupported claims.
"""

    def quiz_questions(

        self,

        context: RetrievedContext,

    ) -> str:

        quiz = self.quiz_generator.generate(
            context,
        )

        if not quiz:

            return "None known for these concepts."

        return "\n".join(

            f"- ({item['difficulty']}) {item['question']} "
            f"[Reference answer: {item['answer']}]"

            for item in quiz
        )

    def socratic_questions(

        self,

        context: RetrievedContext,

    ) -> str:

        questions = []

        for concept in context.concepts:

            questions.extend(
                SOCRATIC_QUESTIONS.get(
                    concept,
                    [],
                )
            )

        if not questions:

            return "None known for these concepts."

        return "\n".join(
            f"- {question}"
            for question in questions
        )

    def analogy_examples(

        self,

        context: RetrievedContext,

    ) -> str:

        analogies = []

        for concept in context.concepts:

            entry = COMMON_ANALOGIES.get(
                concept,
            )

            if entry:

                analogies.append(
                    f"{entry['title']}: {entry['analogy']}"
                )

        if not analogies:

            return "None known for these concepts."

        return "\n".join(
            f"- {analogy}"
            for analogy in analogies
        )

    def misconception_examples(

        self,

        context: RetrievedContext,

    ) -> str:

        examples = []

        for concept in context.concepts:

            examples.extend(
                COMMON_MISCONCEPTIONS.get(
                    concept,
                    [],
                )
            )

        if not examples:

            return "None known for these concepts."

        return "\n".join(
            f"- {example}"
            for example in examples
        )

    def _mode_instruction(

        self,

        mode: TutorMode,

    ) -> str:

        instructions = {

            TutorMode.INTUITION:
                "Explain ideas intuitively before introducing formal definitions.",

            TutorMode.MATHEMATICS:
                "Focus on mathematical derivations and notation.",

            TutorMode.IMPLEMENTATION:
                "Explain implementation details with practical examples.",

            TutorMode.PREREQUISITES:
                "Relate the answer to prerequisite concepts.",

            TutorMode.SUMMARY:
                "Provide a concise summary.",

            TutorMode.ANALOGY: (
                "Teach primarily through analogies. Begin with the "
                "analogy. Then explain how every element of the "
                "analogy maps to the research concept. Finally explain "
                "where the analogy breaks down so the learner does not "
                "overgeneralize."
            ),

            TutorMode.MISCONCEPTION: (
                "Explain the correct concept. Identify whether the "
                "learner's question contains a common misconception. "
                "If so: 1. State the misconception. 2. Explain why it "
                "is incorrect. 3. Explain the correct intuition. "
                "4. End with a mental model."
            ),

            TutorMode.SOCRATIC: (
                "Do not immediately answer the learner. Guide them "
                "through reasoning. Ask one question at a time. Only "
                "reveal explanations after the learner has attempted "
                "an answer. Encourage reflection rather than "
                "memorization."
            ),

            TutorMode.QUIZ: (
                "Do not explain first. Present one quiz question. Wait "
                "for the learner's answer. Afterwards: 1. Evaluate the "
                "answer. 2. Explain why it is correct or incorrect. "
                "3. Reinforce the underlying concept."
            ),

            TutorMode.VISUALIZATION: (
                "Explain the concept visually. Describe the diagram "
                "step-by-step. Clearly identify: 1. Components. "
                "2. Connections. 3. Information flow. 4. Inputs. "
                "5. Outputs. Use simple spatial language so that the "
                "learner could recreate the diagram."
            ),

            TutorMode.COMPARISON: (
                "Compare the requested concepts in a structured way. "
                "Present the comparison using the following sections: "
                "1. Purpose. 2. Core Idea. 3. Similarities. "
                "4. Differences. 5. Advantages. 6. Limitations. "
                "7. Typical Applications. Conclude with guidance on "
                "when a learner should prefer one concept over the "
                "other."
            ),

            TutorMode.EXAMPLE: (
                "Teach using progressively richer examples. Structure "
                "the response as follows: 1. Simple intuition example. "
                "2. Practical real-world example. 3. Research-oriented "
                "example. Clearly explain how each example connects "
                "back to the underlying concept."
            ),
        }

        return instructions[mode]
