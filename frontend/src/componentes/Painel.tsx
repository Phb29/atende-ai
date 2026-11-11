import { useState } from "react";
import type { Acao, Chamado } from "../api";
import { CartaoAcao } from "./CartaoAcao";

type Props = {
  acoes: Acao[];
  chamados: Chamado[];
  ocupado: string | null;
  aoDecidir: (id: string, aprovar: boolean) => void;
  aoPerguntar: (texto: string) => void;
};

export function Painel({ acoes, chamados, ocupado, aoDecidir, aoPerguntar }: Props) {
  const [aba, setAba] = useState<"fila" | "chamados">("fila");
  const pendentes = acoes.filter((a) => a.situacao === "pendente");
  const decididas = acoes.filter((a) => a.situacao !== "pendente").slice(0, 5);

  return (
    <aside className="painel" aria-label="Painel do técnico">
      <div className="abas" role="tablist">
        <button role="tab" aria-selected={aba === "fila"} className={aba === "fila" ? "ativa" : ""} onClick={() => setAba("fila")}>
          Fila de aprovação {pendentes.length > 0 && <span className="contador">{pendentes.length}</span>}
        </button>
        <button role="tab" aria-selected={aba === "chamados"} className={aba === "chamados" ? "ativa" : ""} onClick={() => setAba("chamados")}>
          Chamados <span className="contador neutro">{chamados.length}</span>
        </button>
      </div>

      {aba === "fila" ? (
        <div className="painel-corpo">
          {pendentes.length === 0 ? (
            <p className="vazio">Nenhuma ação esperando. Quando o agente preparar algo que muda dados, aparece aqui.</p>
          ) : (
            pendentes.map((a) => (
              <CartaoAcao key={a.id} acao={a} compacto ocupado={ocupado === a.id} aoDecidir={aoDecidir} />
            ))
          )}
          {decididas.length > 0 && (
            <>
              <h3 className="subtitulo">Decididas há pouco</h3>
              {decididas.map((a) => (
                <CartaoAcao key={a.id} acao={a} compacto ocupado={false} aoDecidir={aoDecidir} />
              ))}
            </>
          )}
        </div>
      ) : (
        <ul className="painel-corpo lista-chamados">
          {chamados.map((c) => (
            <li key={c.numero}>
              <button className="linha-chamado" onClick={() => aoPerguntar(`Qual o status do ${c.numero}?`)} title="Perguntar ao agente">
                <span className={`bolinha ${c.prioridade}`} aria-label={`prioridade ${c.prioridade}`} />
                <span className="chamado-info">
                  <code>{c.numero}</code>
                  <span className="chamado-titulo">{c.titulo}</span>
                </span>
                <span className={`situacao ${c.situacao}`}>{c.situacao_texto}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
