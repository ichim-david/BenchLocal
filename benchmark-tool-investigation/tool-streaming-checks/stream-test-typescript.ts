export interface User {
  id: number;
  name: string;
  email: string;
}

export function formatUser(user: User): string {
  return `${user.name} <${user.email}> (ID: ${user.id})`;
}

const exampleUser: User = {
  id: 1,
  name: "Alice Johnson",
  email: "alice@example.com",
};
