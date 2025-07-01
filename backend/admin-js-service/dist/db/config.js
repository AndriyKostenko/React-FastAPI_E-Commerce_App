const config = {
    type: process.env.DATABASE_DIALECT,
    url: process.env.DATABASE_URL,
    entities: [],
    migrations: [],
    migrationsRun: false,
    migrationsTableName: 'migrations',
    migrationsTransactionMode: 'all',
    subscribers: [],
};
export default config;
