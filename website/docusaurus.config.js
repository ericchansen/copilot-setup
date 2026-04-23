// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'copilot-setup',
  tagline: 'A TUI dashboard for GitHub Copilot CLI configuration',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://ericchansen.github.io',
  baseUrl: '/copilot-setup/',
  organizationName: 'ericchansen',
  projectName: 'copilot-setup',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/ericchansen/copilot-setup/tree/main/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/screenshot.png',
      colorMode: {
        defaultMode: 'dark',
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'copilot-setup',
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'docsSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://github.com/ericchansen/copilot-setup',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {
                label: 'Getting Started',
                to: '/docs/getting-started',
              },
              {
                label: 'Tab Reference',
                to: '/docs/tabs/',
              },
            ],
          },
          {
            title: 'Reference',
            items: [
              {
                label: 'Key Bindings',
                to: '/docs/key-bindings',
              },
              {
                label: 'Doctor Command',
                to: '/docs/doctor',
              },
            ],
          },
          {
            title: 'More',
            items: [
              {
                label: 'GitHub',
                href: 'https://github.com/ericchansen/copilot-setup',
              },
              {
                label: 'PyPI',
                href: 'https://pypi.org/project/copilot-setup/',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Eric Hansen. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ['bash', 'python', 'powershell', 'json'],
      },
    }),
};

export default config;
