import type { Acao } from "../api";

const ROTULO: Record<Acao["tipo"], string> = {
  abrir_chamado: "Abrir chamado",
  resetar_senha: "Resetar senha",
  desbloquear_conta: "Desbloquear conta",
};

type Props = {
  acao: Acao;
  ocupado: boolean;
  aoDecidir: (id: string, aprovar: boolean) => void;
  compacto?: boolean;
};

export function CartaoAcao({ acao, ocupado, aoDecidir, compacto }: Props) {
  return (
    <div className={`cartao-acao ${acao.situacao}${compacto ? " compacto" : ""}`}>
      <div className="cartao-topo">
        <span className="tipo-acao">{ROTULO[acao.tipo]}</span>
        <span className={`selo ${acao.situacao}`}>{acao.situacao}</span>
      </div>
      <p className="cartao-resumo">{acao.resumo}</p>
      {acao.situacao === "pendente" ? (
        <div className="cartao-botoes">
          <button className="botao primario" disabled={ocupado} onClick={() => aoDecidir(acao.id, true)}>
            Aprovar
          </button>
          <button className="botao fantasma" disabled={ocupado} onClick={() => aoDecidir(acao.id, false)}>
            Rejeitar
          </button>
          <code className="id-acao">{acao.id}</code>
        </div>
      ) : (
        acao.resultado && <p className="cartao-resultado">{acao.resultado}</p>
      )}
    </div>
  );
}
