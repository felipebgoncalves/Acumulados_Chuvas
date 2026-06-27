from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


TZ_BRT = ZoneInfo("America/Sao_Paulo")


@dataclass
class FonteStatus:
    fonte: str
    sucesso: bool
    registros: int = 0
    mensagem: str = ""
    atualizado_em: datetime | None = None
    ultima_tentativa: datetime | None = None

    @classmethod
    def sucesso_coleta(cls, fonte: str, registros: int) -> "FonteStatus":
        agora = datetime.now(TZ_BRT)
        return cls(
            fonte=fonte,
            sucesso=True,
            registros=registros,
            mensagem="Coleta realizada com sucesso.",
            atualizado_em=agora,
            ultima_tentativa=agora,
        )

    @classmethod
    def falha_coleta(cls, fonte: str, erro: Exception | str) -> "FonteStatus":
        agora = datetime.now(TZ_BRT)
        return cls(
            fonte=fonte,
            sucesso=False,
            registros=0,
            mensagem=str(erro),
            atualizado_em=None,
            ultima_tentativa=agora,
        )

    def to_dict(self) -> dict:
        return {
            "Fonte": self.fonte,
            "Status": "OK" if self.sucesso else "Falha",
            "Registros": self.registros,
            "Última atualização": self.atualizado_em.strftime("%d/%m/%Y %H:%M:%S")
            if self.atualizado_em
            else "-",
            "Última tentativa": self.ultima_tentativa.strftime("%d/%m/%Y %H:%M:%S")
            if self.ultima_tentativa
            else "-",
            "Mensagem": self.mensagem,
        }
