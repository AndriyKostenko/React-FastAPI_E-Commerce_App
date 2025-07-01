import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn, BaseEntity, Index } from 'typeorm';

@Index('idx_users_email', ['email'])
@Index('idx_users_role', ['role'])
@Index('idx_users_is_active', ['isActive'])
@Index('idx_users_is_verified', ['isVerified'])
@Index('idx_users_date_created', ['dateCreated'])
@Entity({ name: 'users' })
export class User extends BaseEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 50, nullable: false })
  name: string;

  @Column({ type: 'varchar', length: 100, unique: true, nullable: false })
  email: string;

  @Column({ type: 'varchar', nullable: false, name: 'hashed_password'})
  hashedPassword: string;

  @Column({ type: 'varchar', nullable: true })
  role: string | null;

  @Column({ type: 'varchar', nullable: true, name: 'phone_number' })
  phoneNumber: string | null;

  @Column({ type: 'varchar', nullable: true })
  image: string | null;

  @Column({ type: 'boolean', default: true, nullable: false, name: 'is_active' })
  isActive: boolean;

  @Column({ type: 'boolean', default: false, nullable: false, name: 'is_verified' })
  isVerified: boolean;

  @CreateDateColumn({ type: 'timestamp with time zone', name: 'date_created' })
  dateCreated: Date;

  @UpdateDateColumn({ type: 'timestamp with time zone', name: 'date_updated', nullable: true })
  dateUpdated: Date | null;
}