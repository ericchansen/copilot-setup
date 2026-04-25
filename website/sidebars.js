// @ts-check

/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docsSidebar: [
    'getting-started',
    {
      type: 'category',
      label: 'Tabs',
      link: {type: 'doc', id: 'tabs/index'},
      items: [
        'tabs/plugins',
        'tabs/mcp-servers',
        'tabs/skills-agents',
        'tabs/other-tabs',
      ],
    },
    'key-bindings',
    'doctor',
    'troubleshooting',
    'architecture',
  ],
};

export default sidebars;
