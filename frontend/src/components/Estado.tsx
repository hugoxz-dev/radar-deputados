// Os três estados que toda tela precisa ter além do "deu certo":
// carregando, vazio e erro. Centralizados aqui para ficarem iguais no site todo.

export function Carregando({ texto = "Carregando…", altura = "h-40" }: { texto?: string; altura?: string }) {
  return (
    <div role="status" className={`flex ${altura} items-center justify-center gap-3 text-slate-500`}>
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-marca-600" />
      {texto}
    </div>
  );
}

export function Vazio({ titulo, detalhe }: { titulo: string; detalhe?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
      <p className="font-medium text-slate-700">{titulo}</p>
      {detalhe && <p className="mt-1 text-sm text-slate-500">{detalhe}</p>}
    </div>
  );
}

export function Erro({ mensagem, aoTentarDeNovo }: { mensagem: string; aoTentarDeNovo?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-6 py-6 text-center">
      <p className="font-medium text-red-800">Não foi possível carregar os dados.</p>
      <p className="mt-1 text-sm text-red-700">{mensagem}</p>
      {aoTentarDeNovo && (
        <button
          onClick={aoTentarDeNovo}
          className="mt-4 rounded-md bg-white px-4 py-2 text-sm font-medium text-red-800 ring-1 ring-red-300 hover:bg-red-100"
        >
          Tentar de novo
        </button>
      )}
    </div>
  );
}
