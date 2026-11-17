import { Link } from "react-router-dom";

export default function NaoEncontrada() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-bold text-marca-900">Página não encontrada</h1>
      <p className="mt-2 text-slate-600">O endereço não existe ou foi digitado errado.</p>
      <Link to="/" className="mt-6 inline-block text-marca-700 hover:underline">
        Voltar para o início
      </Link>
    </div>
  );
}
