import type { ReactNode } from "react";
import { Link } from "react-router-dom";

// Texto público da metodologia (o mesmo conteúdo de docs/metodologia.md, em linguagem simples).
export default function Metodologia() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 text-slate-700">
      <header className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight text-marca-900">Metodologia</h1>
        <p className="text-lg">Como o Radar encontra os gastos fora do padrão.</p>
        <p className="rounded-md border border-marca-100 bg-marca-50 px-4 py-3">
          <strong>Um gasto fora do padrão não significa irregularidade.</strong> Os destaques são estatísticos: eles
          mostram que um valor é muito diferente do comum, não que seja ilegal. Muitos têm explicação simples, como uma
          viagem longa, um evento ou uma compra anual. Use-os como ponto de partida para consultar a nota original,
          nunca como conclusão.
        </p>
      </header>

      <Secao titulo="De onde vêm os dados">
        <p>
          Todas as despesas vêm da API de Dados Abertos da Câmara dos Deputados: notas fiscais e recibos reembolsados
          pela Cota para o Exercício da Atividade Parlamentar (CEAP) nos últimos 12 meses. O valor considerado é o{" "}
          <strong>valor líquido</strong>: o valor da nota menos a parte que a Câmara não reembolsou (glosa).
        </p>
      </Secao>

      <Secao titulo="As quatro regras">
        <Regra numero={1} titulo="Valor atípico para a categoria no estado">
          <p>
            Destaca uma nota com valor muito maior que as notas da <strong>mesma categoria</strong> apresentadas por
            deputados do <strong>mesmo estado</strong>. A comparação é feita só com o mesmo estado porque o valor da
            cota muda de estado para estado: é maior para quem mora longe de Brasília.
          </p>
          <p>
            O cálculo usa a <strong>mediana</strong> (o valor do meio) e o <strong>desvio absoluto mediano</strong>, um
            "z-score robusto". Diferente da média, a mediana não é puxada para cima pelo próprio valor extremo. A nota é
            destacada quando fica mais de 3,5 "distâncias típicas" acima do normal, o limite recomendado na literatura
            estatística (Iglewicz e Hoaglin).
          </p>
          <p>
            Como a maioria das notas é pequena e poucas são grandes, o cálculo é feito na escala logarítmica. Na prática,
            os destaques ficam entre 5 e 30 vezes acima da mediana. Grupos com menos de 30 notas não são comparados.
          </p>
          <Exemplo>
            Valor de R$ 7.351,90 é 32,0 vezes a mediana de Combustíveis e lubrificantes para deputados de RJ (R$ 230,06).
          </Exemplo>
        </Regra>

        <Regra numero={2} titulo="Concentração em um fornecedor">
          <p>
            Destaca quando um único fornecedor recebe <strong>mais de 40%</strong> do que o deputado gastou numa
            categoria durante o ano, se o gasto passar de R$ 10 mil e tiver pelo menos 5 notas.
          </p>
          <p>
            Em muitas categorias, um fornecedor só é o normal: a operadora de telefone, o aluguel do escritório, a
            locação do carro, as companhias aéreas. Por isso a regra só vale onde <strong>o deputado típico divide os
            gastos</strong> entre vários fornecedores. Esse critério é recalculado a partir dos dados; hoje entram
            combustíveis, hospedagem e alimentação.
          </p>
          <Exemplo>
            O fornecedor POSTO X recebeu 87% do gasto com Combustíveis e lubrificantes em 2026. Nesta categoria, o maior
            fornecedor de um deputado costuma ficar com 24%.
          </Exemplo>
        </Regra>

        <Regra numero={3} titulo="Notas repetidas">
          <p>
            Destaca duas ou mais notas do <strong>mesmo fornecedor</strong>, com o <strong>mesmo valor</strong>, na{" "}
            <strong>mesma data</strong>. Ficam de fora notas abaixo de R$ 100 e as categorias em que isso é rotina:
            passagens (ida e volta custam o mesmo), pedágio, hospedagem (uma nota por diária), telefonia, aluguel e
            locação de veículos.
          </p>
          <Exemplo>2 notas de R$ 7.665,00 do mesmo fornecedor na mesma data (25/08/2026), em Divulgação.</Exemplo>
        </Regra>

        <Regra numero={4} titulo="Gasto mensal atípico">
          <p>
            Destaca um mês em que o <strong>total</strong> gasto pelo deputado ficou muito acima do total dos outros
            deputados do mesmo estado, no mesmo mês. Usa o mesmo z-score robusto (limite 3,5) e exige que o total seja{" "}
            <strong>pelo menos o dobro da mediana</strong> do estado. Só entram meses já consolidados: como as notas
            chegam com até 90 dias de atraso, os meses mais recentes ficam de fora até terem um volume de notas próximo
            do normal.
          </p>
          <Exemplo>
            O gasto total em ago/2026 (R$ 129.940,19) foi 5,7 vezes a mediana dos 14 deputados de PA no mesmo mês (R$
            22.970,83).
          </Exemplo>
        </Regra>
      </Secao>

      <Secao titulo="Limitações">
        <ul className="list-disc space-y-1 pl-5">
          <li>Os números não mostram o contexto: um evento, uma missão ou uma compra anual explicam muitos valores altos.</li>
          <li>As notas chegam com até 90 dias de atraso; os meses recentes ainda estão incompletos.</li>
          <li>
            Os limites são escolhas: valores diferentes gerariam mais ou menos destaques. Os atuais foram calibrados com os
            dados reais.
          </li>
          <li>Os dados são os publicados pela Câmara; erros na fonte aparecem aqui também.</li>
        </ul>
      </Secao>

      <Secao titulo="Atualização">
        <p>
          Os destaques são recalculados depois de cada atualização dos dados. Se um deixa de se aplicar (por exemplo,
          porque a Câmara corrigiu a nota), ele é removido.
        </p>
      </Secao>

      <p>
        <Link to="/alertas" className="font-medium text-marca-700 hover:underline">
          Ver os gastos fora do padrão →
        </Link>
      </p>
    </article>
  );
}

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold text-slate-900">{titulo}</h2>
      {children}
    </section>
  );
}

function Regra({ numero, titulo, children }: { numero: number; titulo: string; children: ReactNode }) {
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="font-semibold text-slate-900">
        <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-marca-100 text-sm text-marca-700">
          {numero}
        </span>
        {titulo}
      </h3>
      {children}
    </div>
  );
}

function Exemplo({ children }: { children: ReactNode }) {
  return <p className="border-l-4 border-marca-100 pl-3 text-sm italic text-slate-600">Exemplo: “{children}”</p>;
}
