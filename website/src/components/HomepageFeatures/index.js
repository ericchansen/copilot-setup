import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    emoji: '📊',
    title: '11 Tabs',
    description:
      'Plugins, MCP servers, skills, agents, settings, and more — all in one dashboard.',
  },
  {
    emoji: '🔍',
    title: 'Instant Filter',
    description:
      'Press / to search across any tab. Results update as you type.',
  },
  {
    emoji: '🩺',
    title: 'Doctor Command',
    description:
      'Probe every MCP server for health — stdio and HTTP — in one command.',
  },
  {
    emoji: '🔌',
    title: 'Plugin Management',
    description:
      'Toggle, upgrade, install, and remove plugins without leaving the terminal.',
  },
];

function Feature({emoji, title, description}) {
  return (
    <div className={styles.featureCard}>
      <div className={styles.featureEmoji}>{emoji}</div>
      <Heading as="h3">{title}</Heading>
      <p>{description}</p>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className={styles.featureGrid}>
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
