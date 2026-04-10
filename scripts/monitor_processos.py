#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import smtplib
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from email.mime.text import MIMEText
from pathlib import Path


@dataclass
class AlertConfig:
    threshold_30: int = 30
    threshold_60: int = 60
    threshold_90: int = 90


REQUIRED_COLUMNS = [
    "id_processo",
    "numero_processo",
    "tipo_processo",
    "prioridade",
    "ultima_movimentacao",
    "responsavel",
]


def calcular_faixa(dias: int, prioridade: str, cfg: AlertConfig) -> str:
    prioridade = (prioridade or "").strip().lower()
    bonus = 10 if prioridade == "alta" else 0
    t30 = max(1, cfg.threshold_30 - bonus)
    t60 = max(1, cfg.threshold_60 - bonus)
    t90 = max(1, cfg.threshold_90 - bonus)

    if dias > t90:
        return "critico_90+"
    if dias > t60:
        return "alto_60+"
    if dias > t30:
        return "medio_30+"
    return "ok"


def sugerir_acao(faixa: str) -> str:
    return {
        "critico_90+": "Peticionar impulso processual e registrar cobrança formal de andamento",
        "alto_60+": "Cobrar andamento com cartório/vara e revisar estratégia",
        "medio_30+": "Revisar autos e preparar minuta de próximo passo",
        "ok": "Sem ação imediata",
    }.get(faixa, "Sem ação imediata")


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Data inválida '{value}'. Use YYYY-MM-DD.") from exc


def carregar_processos(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV sem cabeçalho.")

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

        hoje = date.today()
        rows = []
        for row in reader:
            ultima = parse_date(row["ultima_movimentacao"])
            dias_sem_mov = (hoje - ultima).days
            row["dias_sem_movimentacao"] = dias_sem_mov
            rows.append(row)

    return rows


def processar(rows: list[dict], cfg: AlertConfig, tipo_processo: str | None = None) -> list[dict]:
    filtrados = rows
    if tipo_processo:
        filtrados = [r for r in rows if r["tipo_processo"].strip().lower() == tipo_processo.strip().lower()]

    for row in filtrados:
        faixa = calcular_faixa(int(row["dias_sem_movimentacao"]), row.get("prioridade", ""), cfg)
        row["faixa_alerta"] = faixa
        row["acao_sugerida"] = sugerir_acao(faixa)

    severidade = {"critico_90+": 0, "alto_60+": 1, "medio_30+": 2, "ok": 3}
    filtrados.sort(key=lambda r: (severidade.get(r.get("faixa_alerta", "ok"), 99), -int(r["dias_sem_movimentacao"])))
    return filtrados


def salvar_saida(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(REQUIRED_COLUMNS + ["dias_sem_movimentacao", "faixa_alerta", "acao_sugerida"])
        return

    columns = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def enviar_email_resumo(rows: list[dict]) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    to_email = os.getenv("ALERT_TO")
    from_email = os.getenv("ALERT_FROM", smtp_user)

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass, to_email, from_email]):
        print("[INFO] Variáveis SMTP não definidas; resumo será exibido apenas no terminal.")
        return

    alertas = [r for r in rows if r.get("faixa_alerta") in {"critico_90+", "alto_60+", "medio_30+"}]
    counts = Counter(r["faixa_alerta"] for r in alertas)

    body = [
        "Resumo de processos com possível inatividade:\n",
        f"Total analisado: {len(rows)}",
        f"Total com alerta: {len(alertas)}",
        "",
    ]
    for faixa, qtd in sorted(counts.items()):
        body.append(f"- {faixa}: {qtd}")

    msg = MIMEText("\n".join(body), "plain", "utf-8")
    msg["Subject"] = "[Jurídico] Resumo diário de processos sem movimentação"
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    print(f"[OK] E-mail enviado para {to_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitora processos sem movimentação.")
    parser.add_argument("--input", required=True, help="CSV de entrada")
    parser.add_argument("--output", required=True, help="CSV de saída")
    parser.add_argument("--tipo", required=False, help="Filtro opcional por tipo_processo")
    args = parser.parse_args()

    cfg = AlertConfig()
    rows = carregar_processos(Path(args.input))
    resultado = processar(rows, cfg, args.tipo)
    salvar_saida(resultado, Path(args.output))
    enviar_email_resumo(resultado)

    counts = Counter(r["faixa_alerta"] for r in resultado)
    print("\n[RESUMO]")
    for faixa, qtd in sorted(counts.items()):
        print(f"{faixa}: {qtd}")
    print(f"\nArquivo gerado em: {args.output}")


if __name__ == "__main__":
    main()
