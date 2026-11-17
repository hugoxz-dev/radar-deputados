// Formatação no padrão brasileiro (Intl já sabe usar vírgula decimal, "R$" etc.).

const moedaFmt = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const moedaCompactaFmt = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});
const numeroFmt = new Intl.NumberFormat("pt-BR");

/** 1234.5 -> "R$ 1.234,50" */
export const moeda = (v: number) => moedaFmt.format(v);

/** 214039316 -> "R$ 214 mi" (para cards e eixos de gráfico) */
export const moedaCompacta = (v: number) => moedaCompactaFmt.format(v);

/** 179554 -> "179.554" */
export const numero = (v: number) => numeroFmt.format(v);

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** (2026, 3) -> "mar/26" */
export const mesCurto = (ano: number, mes: number) => `${MESES[mes - 1]}/${String(ano).slice(2)}`;

/** "2025-12" -> "dez/2025" */
export const mesPorExtenso = (aaaaMm: string) => {
  const [ano, mes] = aaaaMm.split("-").map(Number);
  return `${MESES[mes - 1]}/${ano}`;
};

/** "2026-09-19" -> "19/09/2026" (a data vem sem fuso; não usar new Date, que deslocaria o dia) */
export const data = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/** ISO com hora -> "14/11/2026 às 01:12" no fuso de quem está vendo */
export const dataHora = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }).replace(", ", " às ");

/** "33625148000170" -> "33.625.148/0001-70"; CPF -> "***.456.789-**" (CPF parcialmente oculto) */
export function documento(cnpjCpf: string | null): string {
  if (!cnpjCpf) return "—";
  const d = cnpjCpf.replace(/\D/g, "");
  if (d.length === 14) return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  if (d.length === 11) return `***.${d.slice(3, 6)}.${d.slice(6, 9)}-**`;
  return cnpjCpf;
}
