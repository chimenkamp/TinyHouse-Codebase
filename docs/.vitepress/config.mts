import { defineConfig } from 'vitepress';

export default defineConfig({
  title: 'TinyHouse Lab',
  description: 'Documentation for the TinyHouse sensor data lab.',
  cleanUrls: true,
  themeConfig: {
    nav: [
      { text: 'Overview', link: '/' },
      { text: 'Network', link: '/network/' },
      { text: 'MQTT', link: '/mqtt/' },
      { text: 'Operations', link: '/operations/ansible' }
    ],
    sidebar: [
      {
        text: 'Start',
        items: [
          { text: 'Overview', link: '/' }
        ]
      },
      {
        text: 'Architecture',
        items: [
          { text: 'Data Platform', link: '/architecture/data-platform' }
        ]
      },
      {
        text: 'Network',
        items: [
          { text: 'Network Overview', link: '/network/' },
          { text: 'Inventory', link: '/network/inventory' },
          { text: 'Live Findings', link: '/network/live-findings' }
        ]
      },
      {
        text: 'Infrastructure',
        items: [
          { text: 'Management PC', link: '/infrastructure/management-pc' },
          { text: 'Raspberry Pis', link: '/infrastructure/raspberry-pis' }
        ]
      },
      {
        text: 'MQTT',
        items: [
          { text: 'MQTT Overview', link: '/mqtt/' }
        ]
      },
      {
        text: 'Sensors',
        items: [
          { text: 'Sensor Layer', link: '/sensors/' }
        ]
      },
      {
        text: 'Operations',
        items: [
          { text: 'Ansible', link: '/operations/ansible' },
          { text: 'Access', link: '/operations/access' }
        ]
      }
    ],
    search: {
      provider: 'local'
    }
  }
});
