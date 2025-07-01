import { AdminJSOptions } from 'adminjs';

import { User } from '../db/entities.js';

import componentLoader from './component-loader.js';

const options: AdminJSOptions = {
  componentLoader,
  rootPath: '/admin',
  resources: [User],
  databases: [],
};

export default options;
