using LexerModule;

namespace ParserModule.Nodes;

public sealed class IdentifierNode : AstNode
{
    public Token Token { get; }
    public string Name { get; }

    public IdentifierNode(Token token)
    {
        Token = token;
        Name = token.Lexeme;
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIdentifierNode(this);
    }
}