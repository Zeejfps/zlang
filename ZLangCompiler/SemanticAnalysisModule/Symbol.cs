using ParserModule;
using ParserModule.Nodes;

namespace SemanticAnalysisModule;

public class Symbol
{
    public string Name { get; }
    public TypeNode? Type { get; }
    public AstNode DeclaringNode { get; }

    public Symbol(string name, TypeNode? type, AstNode declaringNode)
    {
        Name = name;
        Type = type;
        DeclaringNode = declaringNode;
    }

    public override string ToString()
    {
        return $"{Name} {DeclaringNode.GetType()} -> {Type}";
    }
}