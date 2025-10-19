namespace SemanticAnalysisModule;

class Scope
{
    public Scope? Parent { get; }
    private readonly Dictionary<string, Symbol> _symbols = new();

    public Scope(Scope? parent)
    {
        Parent = parent;
    }

    public bool TryDefine(Symbol sym)
    {
        return _symbols.TryAdd(sym.Name, sym);
    }

    public Symbol? Resolve(string name)
    {
        if (_symbols.TryGetValue(name, out var sym))
            return sym;
        return Parent?.Resolve(name);
    }
}