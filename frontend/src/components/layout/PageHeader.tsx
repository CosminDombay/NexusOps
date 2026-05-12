type PageHeaderProps = {
  title: string;
  description: string;
};

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header className="mb-8">
      <h2 className="text-2xl font-semibold tracking-normal">{title}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">{description}</p>
    </header>
  );
}

