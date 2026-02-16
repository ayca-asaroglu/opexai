"""
Built-in example tools for the orchestration platform.

Extension points:
- Add utility tools or domain-specific function packs.
- Replace these stubs with real business logic.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.functions.registry import FunctionRegistry


class SubmitIdeaFormPayload(BaseModel):
    """
    Input schema for submitting a fully populated idea form.

    Extension points:
    - Add metadata fields such as owner, department, or priority.
    - Add stricter validation rules for individual fields.
    """

    fikrin_ozeti: str = Field(description="Fikrin kisa ve net adi.")
    fikrin_aciklamasi: str = Field(description="Fikrin detayli aciklamasi.")
    amac: Literal[
        "Özel bankacılıkta karlı büyüme",
        "Ticari bankacılıkta karlı büyüme",
        "Tüzel mobilde işbirlikleri yoluyla kazanımın artması ve müşteri aktifliğini artıracak yeni ürünlerin hayata geçmesi",
        "Şubelerin hızını ve satış potansiyelini artıracak veriye dayalı operasyonel karar süreçlerinin otomatik hale getirilmesi",
        "Operasyonel verimlilik için manuel olan süreçlerin teknoloji ile yeniden tasarlanması",
        "Regülatif /Yasal",
        "Müşteri Deneyimini İyileştirme/Memnuniyetini Artırmak",
    ] = Field(description="Fikrin amac kategorisi.")
    problem: str = Field(description="Hedeflenen problem tanimi.")
    cozum_tipi: str = Field(description="Cozum tipi veya yaklasimi.")
    kanallar: list[
        Literal[
            "Çağrı Merkezi",
            "İnternet Bankacılığı",
            "Mobil Bankacılık",
            "Şube",
            "ATM",
            "Web",
            "Video Bankacılık",
            "IVR",
            "Servis Bankacılığı",
        ]
    ] = Field(description="Gelistirmenin kullanilacagi kanallar.")
    mevcut_durum: str = Field(description="Ihtiyacin su anki karsilanma durumu.")
    hedef_kitle: str = Field(description="Hedef kitle tanimi.")
    kpi: str | None = Field(
        default=None,
        description="Opsiyonel KPI veya metrik hedefleri.",
    )


class ScoreComplexityPayload(BaseModel):
    """
    Input schema for complexity scoring output.

    Extension points:
    - Add scoring breakdown fields or rationale metadata.
    - Add validation for required assessment fields.
    """

    Talep_Tipi: Literal["Development", "Development Değil"] = Field(
        description="Talep tipini belirtir."
    )
    Analiz_Notu: str = Field(
        description="Kısa gerekçe",
        max_length=150,
    )
    T_Shirt_Size: Literal["XS", "S", "M", "L"] = Field(
        description="Belirlenen efor büyüklüğü."
    )


def submit_idea_form(
    fikrin_ozeti: str,
    fikrin_aciklamasi: str,
    amac: str,
    problem: str,
    cozum_tipi: str,
    kanallar: list[str],
    mevcut_durum: str,
    hedef_kitle: str,
    kpi: str | None = None,
) -> dict[str, str]:
    """
    Submit a completed idea form to downstream systems.

    Extension points:
    - Persist data to a database or external API.
    - Add validation, deduplication, or workflow triggers.
    """

    _ = (
        fikrin_ozeti,
        fikrin_aciklamasi,
        amac,
        problem,
        cozum_tipi,
        kanallar,
        mevcut_durum,
        hedef_kitle,
        kpi,
    )
    # TODO: Implement persistence or submission logic.
    return {"status": "received"}


def score_complexity(
    Talep_Tipi: str,
    Analiz_Notu: str,
    T_Shirt_Size: str,
) -> dict[str, str]:
    """
    Persist or forward the complexity scoring decision.

    Extension points:
    - Store scoring decisions in a database.
    - Trigger downstream estimation workflows.
    """

    _ = (Talep_Tipi, Analiz_Notu, T_Shirt_Size)
    # TODO: Implement persistence or notification logic.
    return {"status": "scored"}


def register_builtin_tools(registry: FunctionRegistry) -> None:
    """
    Register built-in tools with the registry.

    Extension points:
    - Add or remove tools based on environment settings.
    - Register external integrations or plugins here.
    """

    registry.register(
        name="submit_idea_form",
        func=submit_idea_form,
        description="Formu submit eder.",
        args_schema=SubmitIdeaFormPayload,
    )
    registry.register(
        name="score_complexity",
        func=score_complexity,
        description="Talebi efor büyüklüğüne göre puanlar.",
        args_schema=ScoreComplexityPayload,
    )
