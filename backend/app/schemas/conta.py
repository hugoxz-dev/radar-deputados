"""Schemas de conta: cadastro, login, usuário, planos e assinatura."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CadastroIn(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: EmailStr
    senha: str = Field(min_length=8, description="Mínimo de 8 caracteres")

    @field_validator("senha")
    @classmethod
    def senha_cabe_no_bcrypt(cls, senha: str) -> str:
        # O bcrypt só aceita até 72 bytes (acentos ocupam 2 bytes); acima disso ele recusa.
        if len(senha.encode("utf-8")) > 72:
            raise ValueError("A senha pode ter no máximo 72 bytes (cerca de 70 caracteres).")
        return senha

    @field_validator("email")
    @classmethod
    def email_minusculo(cls, email: str) -> str:
        return email.lower()  # "Fulano@X.com" e "fulano@x.com" são a mesma conta


class LoginIn(BaseModel):
    email: EmailStr
    senha: str

    @field_validator("email")
    @classmethod
    def email_minusculo(cls, email: str) -> str:
        return email.lower()


class AssinaturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    provedor: str
    inicio: datetime | None
    fim: datetime | None


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    plano: str
    criado_em: datetime
    assinatura: AssinaturaOut | None = None  # a assinatura ativa, se houver


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class PlanoInfo(BaseModel):
    id: str
    nome: str
    preco_mensal: float  # em reais
    recursos: list[str]


class PlanosOut(BaseModel):
    modo_pagamento: str  # "simulado" | "stripe"
    planos: list[PlanoInfo]


class AssinaturaResultado(BaseModel):
    modo: str
    plano: str
    checkout_url: str | None
    mensagem: str
