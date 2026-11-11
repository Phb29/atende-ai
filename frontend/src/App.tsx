import { useCallback, useEffect, useRef, useState } from "react";
import { api, conversarEmFluxo, ErroApi, type Acao, type Chamado, type Meta, type Status } from "./api";
import { CartaoAcao } from "./componentes/CartaoAcao";
import { Painel } from "./componentes/Painel";
import { Texto } from "./componentes/Texto";

type Fala = { id: string; papel: "user" | "assistant"; texto: string; meta?: Meta; erro?: boolean };

const SUGESTOES = [
  { titulo: "Consultar chamado", texto: "Qual o status do CH-5001?" },
  { titulo: "Ver equipamento", texto: "O notebook PAT-3002 está na garantia?" },
  { titulo: "Tirar dúvida", texto: "A VPN fica caindo, o que eu faço?" },
  { titulo: "Resetar senha", texto: "Esqueci minha senha, matrícula U-101" },
];
const LIMITE = 2000;
const CHAVE_MEMORIA = "atende-ai:conversa";

function lerMemoria(): Fala[] {
  try {
    return JSON.parse(localStorage.getItem(CHAVE_MEMORIA) ?? "[]");
  } catch {
    return [];
  }
}

export function App() {
  const [falas, setFalas] = useState<Fala[]>(lerMemoria);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [acoes, setAcoes] = useState<Acao[]>([]);
  const [chamados, setChamados] = useState<Chamado[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ texto: string; tipo: "ok" | "erro" } | null>(null);
  const [painelAberto, setPainelAberto] = useState(false);
  const [rastroAberto, setRastroAberto] = useState<string | null>(null);
  const campo = useRef<HTMLTextAreaElement>(null);
  const fim = useRef<HTMLDivElement>(null);
  const cancelar = useRef<AbortController | null>(null);

  const recarregar = useCallback(() => {
    api.acoes().then(setAcoes).catch(() => {});
    api.chamados().then(setChamados).catch(() => {});
  }, []);

  useEffect(() => {
    recarregar();
    api.status().then(setStatus).catch(() => setStatus(null));
  }, [recarregar]);

  useEffect(() => {
    try {
      localStorage.setItem(CHAVE_MEMORIA, JSON.stringify(falas.slice(-40)));
    } catch {
      /* sem armazenamento: a conversa só não fica salva */
    }
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [falas]);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), 3500);
    return () => clearTimeout(t);
  }, [aviso]);

  // Atalho: "/" em qualquer lugar foca a caixa de mensagem.
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        campo.current?.focus();
      }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, []);

  // A caixa cresce conforme o texto, até um limite.
  useEffect(() => {
    const el = campo.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [texto]);

  async function enviar(mensagem: string) {
    const limpa = mensagem.trim();
    if (!limpa || enviando) return;
    const historico = falas.filter((f) => !f.erro).slice(-6).map((f) => ({ role: f.papel, content: f.texto }));
    const idResposta = crypto.randomUUID();
    setFalas((f) => [...f, { id: crypto.randomUUID(), papel: "user", texto: limpa }, { id: idResposta, papel: "assistant", texto: "" }]);
    setTexto("");
    setEnviando(true);
    cancelar.current = new AbortController();
    const mudar = (fn: (f: Fala) => Fala) => setFalas((todas) => todas.map((f) => (f.id === idResposta ? fn(f) : f)));
    try {
      await conversarEmFluxo(
        limpa,
        historico,
        (meta) => {
          mudar((f) => ({ ...f, meta }));
          if (meta.acao) setAcoes((a) => [meta.acao!, ...a]);
        },
        (pedaco) => mudar((f) => ({ ...f, texto: f.texto + pedaco })),
        cancelar.current.signal,
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        mudar((f) => ({ ...f, texto: f.texto || "Resposta cancelada.", erro: !f.texto }));
      } else {
        const msg = e instanceof ErroApi ? e.message : "Não consegui falar com o servidor. Ele está ligado?";
        mudar((f) => ({ ...f, texto: msg, erro: true }));
      }
    } finally {
      setEnviando(false);
      cancelar.current = null;
    }
  }

  async function decidir(id: string, aprovar: boolean) {
    setOcupado(id);
    try {
      const nova = await api.decidir(id, aprovar);
      setAcoes((todas) => todas.map((a) => (a.id === id ? nova : a)));
      setAviso({ texto: nova.resultado ?? "Feito.", tipo: "ok" });
      if (aprovar) api.chamados().then(setChamados).catch(() => {});
    } catch (e) {
      setAviso({ texto: e instanceof Error ? e.message : "Falhou.", tipo: "erro" });
      recarregar();
    } finally {
      setOcupado(null);
    }
  }

  function novaConversa() {
    cancelar.current?.abort();
    setFalas([]);
    setTexto("");
    campo.current?.focus();
  }

  const pendentes = acoes.filter((a) => a.situacao === "pendente").length;
  const acaoAtual = (a: Acao) => acoes.find((x) => x.id === a.id) ?? a;
  const corStatus = !status ? "fora" : status.usa_ia && !status.ia_disponivel ? "alerta" : "ok";

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <img src="/icone.svg" alt="" width={28} height={28} />
          <span>
            Atende<b>.ai</b>
          </span>
        </div>
        <div className="topo-direita">
          <span className={`provedor ${corStatus}`} title={status?.usa_ia && !status.ia_disponivel ? "A IA não respondeu: o agente usa textos prontos" : undefined}>
            <span className="ponto" />
            {status ? (status.usa_ia ? status.provedor : "modo regras (sem IA)") : "servidor desligado"}
          </span>
          <button className="botao fantasma" onClick={novaConversa}>
            Nova conversa
          </button>
          <button className="botao fantasma so-celular" onClick={() => setPainelAberto((v) => !v)} aria-expanded={painelAberto}>
            Fila {pendentes > 0 && <span className="contador">{pendentes}</span>}
          </button>
        </div>
      </header>

      <main className="corpo">
        <section className="conversa" aria-live="polite">
          {falas.length === 0 ? (
            <div className="boas-vindas">
              <h1>Como posso ajudar no suporte hoje?</h1>
              <p>Consulto chamados e equipamentos, respondo dúvidas com base na base de soluções e preparo ações que você aprova.</p>
              <div className="sugestoes">
                {SUGESTOES.map((s) => (
                  <button key={s.texto} className="sugestao" onClick={() => enviar(s.texto)}>
                    <span className="sugestao-titulo">{s.titulo}</span>
                    <span className="sugestao-texto">{s.texto}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="falas">
              {falas.map((f) => (
                <article key={f.id} className={`fala ${f.papel}${f.erro ? " erro" : ""}`}>
                  {f.papel === "assistant" && <div className="avatar" aria-hidden>A</div>}
                  <div className="balao">
                    {f.texto ? <Texto texto={f.texto} fontes={f.meta?.fontes} /> : <span className="digitando" aria-label="Pensando"><i /><i /><i /></span>}
                    {f.meta?.acao && (
                      <CartaoAcao acao={acaoAtual(f.meta.acao)} ocupado={ocupado === f.meta.acao.id} aoDecidir={decidir} />
                    )}
                    {f.meta && f.texto && (
                      <div className="rodape-fala">
                        <button className="link" onClick={() => setRastroAberto(rastroAberto === f.id ? null : f.id)} aria-expanded={rastroAberto === f.id}>
                          {rastroAberto === f.id ? "ocultar caminho" : "ver caminho do agente"}
                        </button>
                        <span className="via">via {f.meta.provedor}</span>
                        <button className="link" onClick={() => navigator.clipboard?.writeText(f.texto).then(() => setAviso({ texto: "Resposta copiada.", tipo: "ok" }))}>
                          copiar
                        </button>
                      </div>
                    )}
                    {rastroAberto === f.id && f.meta && (
                      <ol className="rastro">
                        {f.meta.passos.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                        <li className="id-req">requisição {f.meta.id_requisicao}</li>
                      </ol>
                    )}
                  </div>
                </article>
              ))}
              <div ref={fim} />
            </div>
          )}

          <form
            className="compositor"
            onSubmit={(e) => {
              e.preventDefault();
              enviar(texto);
            }}
          >
            <textarea
              ref={campo}
              value={texto}
              maxLength={LIMITE}
              rows={1}
              autoFocus
              placeholder="Descreva o problema ou cite um CH-0000, PAT-0000 ou U-000…"
              aria-label="Mensagem"
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  enviar(texto);
                }
                if (e.key === "Escape") setTexto("");
              }}
            />
            {enviando ? (
              <button type="button" className="botao fantasma" onClick={() => cancelar.current?.abort()}>
                Parar
              </button>
            ) : (
              <button type="submit" className="botao primario" disabled={!texto.trim()}>
                Enviar
              </button>
            )}
          </form>
          <p className="dica">
            <kbd>Enter</kbd> envia · <kbd>Shift</kbd>+<kbd>Enter</kbd> quebra linha · <kbd>/</kbd> foca · <kbd>Esc</kbd> limpa
            {texto.length > LIMITE * 0.8 && <span className="contagem"> · {texto.length}/{LIMITE}</span>}
          </p>
        </section>

        <div className={`painel-envoltorio${painelAberto ? " aberto" : ""}`}>
          <Painel acoes={acoes} chamados={chamados} ocupado={ocupado} aoDecidir={decidir} aoPerguntar={(t) => { setPainelAberto(false); enviar(t); }} />
        </div>
      </main>

      {aviso && (
        <div className={`aviso ${aviso.tipo}`} role="status">
          {aviso.texto}
        </div>
      )}
    </div>
  );
}
