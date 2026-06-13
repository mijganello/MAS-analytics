from __future__ import annotations
from typing import Any
from app.tools.registry import tool


@tool(departments=["qual_analysis"])
def analyze_sentiment(texts: list, granularity: str = "document") -> dict[str, Any]:
    """Analyze sentiment using VADER. Returns compound score and label."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        results = []
        for text in texts[:50]:  # Limit to 50 texts
            scores = analyzer.polarity_scores(str(text))
            compound = scores["compound"]
            label = "positive" if compound >= 0.05 else "negative" if compound <= -0.05 else "neutral"
            results.append({
                "text_preview": str(text)[:100],
                "compound": round(compound, 4),
                "label": label,
                "positive": round(scores["pos"], 3),
                "negative": round(scores["neg"], 3),
                "neutral": round(scores["neu"], 3),
            })

        compounds = [r["compound"] for r in results]
        avg = sum(compounds) / len(compounds) if compounds else 0
        return {
            "granularity": granularity,
            "results": results,
            "average_compound": round(avg, 4),
            "overall_label": "positive" if avg >= 0.05 else "negative" if avg <= -0.05 else "neutral",
        }
    except Exception as e:
        return {"error": str(e)}


@tool(departments=["qual_analysis"])
def extract_keywords(text: str, method: str = "freq", top_k: int = 10) -> list[dict[str, Any]]:
    """Extract top keywords with relevance scores using TF-based frequency analysis."""
    try:
        import re
        from collections import Counter
        words = re.findall(r'\b[а-яёА-ЯЁa-zA-Z]{4,}\b', text)
        if not words:
            return []
        freq = Counter(words)
        total = len(words)
        return [{"keyword": w, "score": round(c / total, 4)} for w, c in freq.most_common(top_k)]
    except Exception as e:
        return [{"error": str(e)}]


@tool(departments=["qual_analysis"])
def summarize_text_extractive(text: str, max_sentences: int = 5) -> dict[str, Any]:
    """Extractive summarization using sentence scoring (TF-IDF-like)."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= max_sentences:
        return {"summary": text, "sentences_used": len(sentences)}

    # Score sentences by keyword frequency
    from collections import Counter
    words = re.findall(r'\b[а-яёА-ЯЁa-zA-Z]{3,}\b', text.lower())
    freq = Counter(words)

    scored = []
    for i, sent in enumerate(sentences):
        sent_words = re.findall(r'\b[а-яёА-ЯЁa-zA-Z]{3,}\b', sent.lower())
        score = sum(freq[w] for w in sent_words) / max(len(sent_words), 1)
        # Bonus for first and last sentences
        if i == 0 or i == len(sentences) - 1:
            score *= 1.3
        scored.append((score, i, sent))

    top = sorted(scored, reverse=True)[:max_sentences]
    top_sorted = sorted(top, key=lambda x: x[1])
    summary = " ".join(s for _, _, s in top_sorted)
    return {"summary": summary, "sentences_used": max_sentences}


@tool(departments=["qual_analysis"])
def extract_named_entities(text: str) -> list[dict[str, Any]]:
    """Extract named entities: organizations, dates, numbers, persons."""
    import re
    entities = []
    # Simple rule-based for now (spaCy optional)
    # Numbers with context
    for match in re.finditer(r'\b(\d{1,3}(?:[,\s]\d{3})*(?:[.,]\d+)?)\s*(%|млн|млрд|тыс|руб|$|€)?', text):
        entities.append({
            "text": match.group(0).strip(),
            "type": "NUMBER",
            "start": match.start(),
        })
    # Dates
    for match in re.finditer(r'\b(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}\s*г(?:од)?\.?|\bQ[1-4]\s*\d{4}\b)', text, re.IGNORECASE):
        entities.append({"text": match.group(0), "type": "DATE", "start": match.start()})

    return entities[:50]


@tool(departments=["qual_analysis"])
def analyze_risk_factors(text: str) -> list[dict[str, Any]]:
    """Identify risk factors and their severity in text."""
    import re
    risk_keywords = {
        "critical": ["банкротство", "дефолт", "кризис", "collapse", "bankrupt", "critical failure", "критический"],
        "high": ["риск", "угроза", "снижение", "убыток", "потеря", "risk", "threat", "loss", "decline"],
        "medium": ["нестабильность", "волатильность", "неопределённость", "uncertainty", "volatility"],
        "low": ["возможное", "потенциальное", "незначительное", "minor", "potential"],
    }

    sentences = re.split(r'(?<=[.!?])\s+', text)
    risks = []
    for sent in sentences:
        sent_lower = sent.lower()
        for severity, keywords in risk_keywords.items():
            if any(kw in sent_lower for kw in keywords):
                risks.append({
                    "text": sent.strip(),
                    "severity": severity,
                    "matched_keywords": [kw for kw in keywords if kw in sent_lower],
                })
                break

    return risks[:20]
