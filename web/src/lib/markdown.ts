// Markdown en línea de los README (negritas, código y enlaces) a HTML escapado.
// Los README son fuente de confianza, pero se escapan igual: solo pasan estas tres marcas.

const escapar = (texto: string): string =>
  texto.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] ?? c);

export const enLinea = (texto: string): string =>
  escapar(texto)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" rel="noopener">$1</a>')
    .replace(/(?<![">])(https?:\/\/[^\s<)]+)/g, '<a href="$1" rel="noopener">$1</a>');

export const textoPlano = (texto: string): string =>
  texto.replace(/`([^`]+)`/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1");
