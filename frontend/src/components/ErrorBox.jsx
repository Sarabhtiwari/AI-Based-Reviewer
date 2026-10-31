export default function ErrorBox({ message }) {
  if (!message) return null;
  return (
    <div role="alert" className="my-4 rounded border-l-4 border-conflict bg-red-50 px-4 py-3">
      {message}
    </div>
  );
}