import type { Fonte } from "../api";

// Mostra **negrito** e transforma [KB-01] numa etiqueta com o título do artigo.
// Monta elementos React (não usa innerHTML), então texto vindo da IA não injeta HTML.
export function Texto({ texto, fontes = [] }: { texto: string; fontes?: Fonte[] }) {
  const partes = texto.split(/(\*\*[^*]+\*\*|\[KB-\d{2}\])/g);
  return (
    <>
      {partes.map((p, i) => {
        if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
        const kb = /^\[(KB-\d{2})\]$/.exec(p);
        if (kb) {
          const titulo = fontes.find((f) => f.id === kb[1])?.titulo;
          return (
            <span key={i} className="citacao" title={titulo ?? "Artigo da base de soluções"}>
              {kb[1]}
            </span>
          );
        }
        return <span key={i}>{p}</span>;
      })}
    </>
  );
}
