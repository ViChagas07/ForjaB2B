// Configuracao do SVGO para as ilustracoes do catalogo (Prompt 10, B3).
// Preserva o viewBox, role, title e a paleta; remove apenas metadados mortos.
export default {
  multipass: true,
  plugins: [
    {
      name: "preset-default",
      params: {
        overrides: {
          // NAO remover o viewBox (usado em <img> responsivo).
          removeViewBox: false,
          // NAO remover role/title (acessibilidade obrigatoria).
          removeUnknownsAndDefaults: {
            keepRoleAttr: true,
            keepAriaAttrs: true,
          },
          removeUselessStrokeAndFill: false,
        },
      },
    },
  ],
};
