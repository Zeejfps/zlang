using ParserModule;
using ParserModule.Nodes;

namespace SemanticAnalysisModule;

class Symbol
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
}