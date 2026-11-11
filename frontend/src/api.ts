// Conversa com o backend. Toda rota /api leva o cabeçalho X-API-Key.

const CHAVE = import.meta.env.VITE_CHAVE_API ?? "demo-key";

export type Acao = {
  id: string;
  tipo: "abrir_chamado" | "resetar_senha" | "desbloquear_conta";
  resumo: string;
  situacao: "pendente" | "aprovada" | "rejeitada";
  resultado: string | null;
  criada_em: string;
};

export type Chamado = {
  numero: string;
  titulo: string;
  situacao: string;
  situacao_texto: string;
  prioridade: "baixa" | "media" | "alta";
  tecnico: string | null;
  criado_em: string;
};

export type Fonte = { id: string; titulo: string };

export type Meta = {
  intencao: string;
  passos: string[];
  fontes: Fonte[];
  acao: Acao | null;
  provedor: string;
  id_requisicao: string;
};

export type Status = { provedor: string; usa_ia: boolean; ia_disponivel: boolean };

export class ErroApi extends Error {
  constructor(public codigo: string, mensagem: string) {
    super(mensagem);
  }
}

async function pedir<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const r = await fetch(caminho, {
    ...opcoes,
    headers: { "Content-Type": "application/json", "X-API-Key": CHAVE, ...opcoes.headers },
  });
  if (!r.ok) {
    const corpo = await r.json().catch(() => null);
    throw new ErroApi(corpo?.erro?.codigo ?? "ERRO", corpo?.erro?.mensagem ?? `Erro ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  status: () => pedir<Status>("/pronto"),
  chamados: () => pedir<Chamado[]>("/api/chamados"),
  acoes: () => pedir<Acao[]>("/api/acoes"),
  decidir: (id: string, aprovar: boolean) =>
    pedir<Acao>(`/api/acoes/${id}/${aprovar ? "aprovar" : "rejeitar"}`, { method: "POST" }),
};

// Lê a resposta aos poucos (SSE). Chama aoIniciar com os metadados e aoTexto a cada pedaço.
export async function conversarEmFluxo(
  mensagem: string,
  historico: { role: "user" | "assistant"; content: string }[],
  aoIniciar: (m: Meta) => void,
  aoTexto: (pedaco: string) => void,
  sinal?: AbortSignal,
): Promise<void> {
  const r = await fetch("/api/conversa/fluxo", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": CHAVE },
    body: JSON.stringify({ mensagem, historico }),
    signal: sinal,
  });
  if (!r.ok || !r.body) {
    const corpo = await r.json().catch(() => null);
    throw new ErroApi(corpo?.erro?.codigo ?? "ERRO", corpo?.erro?.mensagem ?? `Erro ${r.status}`);
  }
  const leitor = r.body.pipeThrough(new TextDecoderStream()).getReader();
  let sobra = "";
  for (;;) {
    const { value, done } = await leitor.read();
    if (done) break;
    sobra += value;
    const blocos = sobra.split("\n\n");
    sobra = blocos.pop() ?? "";
    for (const bloco of blocos) {
      const evento = /^event: (.+)$/m.exec(bloco)?.[1];
      const dado = /^data: (.*)$/m.exec(bloco)?.[1];
      if (!evento || dado === undefined) continue;
      if (evento === "inicio") aoIniciar(JSON.parse(dado));
      if (evento === "texto") aoTexto(JSON.parse(dado));
    }
  }
}
